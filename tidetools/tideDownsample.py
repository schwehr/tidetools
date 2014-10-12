#!/usr/bin/env python
"""TODO: Describe module."""

import time
import datetime
from optparse import OptionParser
import os
import string
import sys

import numpy as np
from tideLib import *


def CommandLine():
    '''
    Process the command line options and arguments
    '''

    global options,args

    p = OptionParser()
    p.add_option("-i", "--inputFiles",
                 type="string",
                 dest="inputFiles",
                 action="append",
                 default=[],
                 help="the files to read",
                 metavar="FILE")
    p.add_option('-I','--InputFormat'
                      ,dest='timeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'Input time format. One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
    p.add_option("-o", "--outputFile",
                 default = None,
                 type="string", dest="outputFile",
                 help="the file to write to (overwrites)",
                 metavar="FILE")
    p.add_option('-O','--OutputFormat'
                      ,dest='OtimeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'Output time format. One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
    p.add_option("-S", "--StartTime", type="string", default='00:00:00',
                 dest="startTime",
                 help='''HH:MM:SS for start time of resample''')
    p.add_option("-T", "--Tinterval", type="string", default='00:06:00',
                 dest="interval",
                 help='''HH:MM:SS for resampling interval.
(Fractional seconds are not supported.)''')
    p.add_option("-X", "--debug", type="int", default=0,
                 dest="debug",
                 help="debug level: 0 is off; powers of 2 for levels")
    p.add_option("-v", "--verbose", action="store_true", default=False,
                 dest="verbose",
                 help="")
    p.add_option("--FieldSeperator", default = '\t',
                 type="string", dest="fieldSep",
                 help="the character(s) used to separate fields in the output; [default '\t']")
    p.add_option("--RecordSeperator", default = '\n',
                 type="string", dest="recSep",
                 help="the character(s) used to separate records in the output; [default '\n']")




    (options,args) = p.parse_args()

    return(p)

######################### main ##########################################

def main():

    global options, args

    global inF, outF , errF


    errF = sys.stderr
    p = CommandLine()

    smp = Resampler(iTformat=options.timeFormat
                    ,oTformat=options.OtimeFormat
                    ,start=options.startTime
                    ,interval=options.interval)


    # open output
    if(options.outputFile != None):
        outF = open(options.outputFile,"w")
    else:
        outF = sys.stdout


    # process the input files
    filelist = args + options.inputFiles

    for file in filelist:
        inF = open(file,"r")
        smp.process(inF,outF) # process the file
        inF.close()

    outF.close()


class Resampler():

    def __init__(self,
                 iTformat='caris',
                 oTformat='caris',
                 start='00:00:00',
                 interval='00:06:00'):
        self.iTformat = iTformat
        self.oTformat = oTformat

        # build list of output times over a day
        startSecs = self.timeStr2seconds(start)
        intervalSecs = self.timeStr2seconds(interval)
        outTime = datetime.timedelta(seconds=startSecs)
        self.outTimeList = [outTime]
        endTime = datetime.timedelta(days=1)
        while (outTime < endTime):
            outTime = outTime + datetime.timedelta(seconds=intervalSecs)
            self.outTimeList.append(outTime)

        self.halfTinterval = datetime.timedelta(seconds = (intervalSecs / 2.0))
        self.startTD = None

        # the data and time sample window
        self.reset()
        self.current = np.array([]) # row: DTtime, epochTime, value

    def timeStr2seconds(self,timeStr):
        '''
        parses the timeStr (format HH:MM:SS) and
        converts it into seconds
        '''
        (hours,minutes,seconds) = string.split(timeStr,sep=':')
        return (60.*60.* float(hours) + 60. * float(minutes) + float(seconds))

    def datetime2epoch(self,dt):
        '''
        converts a datetime object into epoch time
        '''
        return time.mktime(dt.timetuple())

    def epoch2datetime(et):
        '''
        converts epoch time to a datetime object
        '''
        return datetime.datetime.utcfromtimestamp(et)

    def process(self,infile,outfile):
        '''
        process the input and print out the interpolate
        data based on the time interval of the first maxTimeSamples
        '''

        global options

        lastOutputDT = None # used to keep track of what's been done

        # the big loop through the data
        for line in inF:
            line.strip()

            if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue # not a data record line

            (dt,value,otherFields) = findTideFields(line,self.iTformat)
            if self.startTD == None:
                # start timedate is set to begining of first day of data
                self.startTD = datetime.datetime(year=dt.year,
                                                 month=dt.month,
                                                 day=dt.day)
            epochtime = self.datetime2epoch(dt)
            self.current = np.array([dt,epochtime,value])


            outputDT = self.outputDateTime(dt)

            # the key situation for doing the statistics
            # when we are halfway to the next scheduled datetime
            if (outputDT != lastOutputDT) and \
                    (dt > (self.halfTinterval + outputDT)):
                # we have passed the threshold for doing output for the
                # nextOutputTime
                (otime,ovalue) = self.align(outputDT)
                if(ovalue != None):
                    tideOutput(outfile,
                               timeFormat=self.oTformat,
                               dTime=otime,
                               waterlevel=ovalue,
                               fieldSep=options.fieldSep,
                               recSep=options.recSep)

                self.reset()
                lastOutputDT = outputDT # mark this one done

            self.windowPush() # add the current data to the window

    def outputDateTime(self,dt):
        '''
        determines which outputDateTime should be associated
        with the given datetime
        '''
        hms = datetime.timedelta(seconds=(dt.second
                                          + dt.minute * 60
                                          + dt.hour * 60 * 60),
                                 microseconds=(dt.microsecond))

        # find next output time which should be one earlier than
        # when outTimeList[n] < hms
        n = 0
        for nextOt in self.outTimeList:
            if(nextOt > hms): break
            n += 1

        # Combine time.date.
        outputDate = datetime.datetime(year=dt.year,
                                       month=dt.month,
                                       day= dt.day)
        # With the previous outTimeList entry
        return(outputDate + self.outTimeList[n-1])

    def windowPush(self):
        '''
        pushes the current time/data set onto the queue
        '''
        if len(self.window) == 0:
            self.window = np.array([self.current])
        else:
            self.window = np.vstack((self.window,self.current))

    def threshold(self):
        '''
        window first time (in seconds) + the interval
        '''
        if len(self.window) > 0:
            return (self.window[0,1] + self.intervalSecs)
        else:
            return self.interval.Secs

    def align(self,time):
        '''
        using the line equation from a least squares fit to the
        data in the window, the value at the prescribed time is
        estimated. output is the time prescribed and the estimated
        value. (Epoch time is used in the fit and the solution.)
        '''

        if len(self.window) == 0: return (None,None)

        times = list(self.window[:,1])
        values= list(self.window[:,2])
        if len(times) == 1:
            value = values[0]
        else:
            (m,b) = np.polyfit(times,values,1) # linear fit
            epochT = self.datetime2epoch(time)
            value = m * epochT + b
        return(time,value)

    def reset(self):
        '''
        clears the window of data
        '''
        self.window = np.array([])


if __name__ == '__main__':
    main()

