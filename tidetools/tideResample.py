#!/usr/bin/env python
"""TODO: Describe module."""

import time
import datetime
import os
import sys
import numpy as np
from tideLib import *
from optparse import OptionParser


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
                      ,help= 'Output time format. One of ' + \
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
                 ,help= 'Output time format. One of ' +\
                     ', '.join(timeTypes)+ ' [default: %default] ')

    p.add_option("-T", "--Tinterval",
                 type="string",
                 default=None,
                 dest="interval",
                 help='''HH:MM:SS for sampling interval.
Sampling intervals greater than the input interval mode result in
realignment. (See the --StartTime option). Sampling intervals less
than or equal the input interval mode result in simple straight-line
interpolation. If no sampling interval is specified, the input interval mode
is used by default.''')

    p.add_option("-S", "--StartTime",
                 type="string",
                 default='00:00:00',
                 dest="startTime",
                 help='''HH:MM:SS for start time of resample''')

    p.add_option("-R", "--Report",
                 default=None,
                 type="string",
                 dest="reportFile",
                 help='''filename for report on points inserted into data.''',
                 metavar="FILE")
    p.add_option("-s", "--maxSamples",
                 type="int",
                 default=500,
                 dest="maxSamples",
                 help='''the maximum number of entries to sample
to determine the modal time interval''')
    p.add_option("-L", "--LeastSquaresAverage",
                 action="store_true",
                 default=False,
                 dest="lsa",
                 help="Use least squares averaging instead of simple averaging")
    p.add_option("-X", "--debug",
                 type="int",
                 default=0,
                 dest="debug",
                 help="debug level: 0 is off; powers of 2 for levels")

    p.add_option("-v", "--verbose",
                 action="store_true",
                 default=False,
                 dest="verbose",
                 help="")

    p.add_option('-f','--timeFormat'
                      ,dest='timeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')

    p.add_option("--FieldSeperator",
                 default = '\t',
                 type="string",
                 dest="fieldSep",
                 help="the character(s) used to separate fields in the output; [default '\t']")

    p.add_option("--RecordSeperator",
                 default = '\n',
                 type="string",
                 dest="recSep",
                 help="the character(s) used to separate records in the output; [default '\n']")


    (options,args) = p.parse_args()

    return(p)


def main():

    global options, args

    global inF, outF , errF , reportF


    errF = sys.stderr

    p = CommandLine()
    # change options.interval into a datetime.timedelta value
    if options.interval != None:
        dtIntervalSpec = datetime.timedelta(seconds =
                                            timeStr2seconds(options.interval))
    else:
        dtIntervalSpec = datetime.timedelta(seconds = 0 )

    # change the start time into a datetime.timedelta value
    dtStartTime = datetime.timedelta(seconds=timeStr2seconds(options.startTime))

    # open output
    if(options.outputFile != None):
        outF = open(options.outputFile,"w")
    else:
        outF = sys.stdout

    # open report file, if specified
    if(options.reportFile != None):
        reportF = open(options.reportFile,"w")

    # process the input files
    filelist = args + options.inputFiles

    fileCount = 0
    for file in filelist:
        inF = open(file,"r")

        # look at the time interval used by the file
        dtInterval = sampleTimedelta(inF,options)

        if options.verbose:
            sys.stderr.write("specified interval %s <= existing interval %s ? %s\n\n"
                % (dtIntervalSpec,dtInterval,(dtIntervalSpec<=dtInterval)))
        # determine if this is a DOWNsample or an interpolation (UPsample)
        # dtInterval is from the sample, dtIntervalSpec is from options spec
        if dtIntervalSpec <= dtInterval:
            # interpolation
            itr = Interpolator(iTformat=options.timeFormat,
                               oTformat=options.OtimeFormat,
                               dtStart=dtStartTime,
                               dtInterval=dtInterval) # use the small interval
            itr.process(inF,outF) # Interpolate

        else:
            # downsample
            smp = Downsampler(iTformat=options.timeFormat,
                              oTformat=options.OtimeFormat,
                              dtStart=dtStartTime,
                              dtInterval=dtIntervalSpec) # use the large interval
            smp.process(inF,outF) # Downsample

        inF.close()
        fileCount += 1

    outF.close()


def resequence(filename,timeFormat):
    '''
    sorts the datafile by time
    '''

    None # not yet implemented


class Interpolator():

    global options

    def __init__(self,
                 iTformat='caris',
                 oTformat='caris',
                 dtStart=datetime.timedelta(seconds=0),
                 dtInterval=datetime.timedelta(seconds=3600)):

        self.iTformat = iTformat
        self.oTformat = oTformat
        self.dtStart = dtStart
        self.dtInterval = dtInterval

        # build list of output times over a day
        intervalSecs = dtInterval.seconds
        outTime = dtStart
        self.outTimeList = [outTime]
        endTime = datetime.timedelta(days=1)
        while (outTime < endTime):
            outTime = outTime + datetime.timedelta(seconds=intervalSecs)
            self.outTimeList.append(outTime)

        self.halfTinterval = datetime.timedelta(seconds = (intervalSecs / 2.0))
        self.startTD = None

    def process(self,infile,outfile):
        '''
        process the input and print out the interpolate
        data based on the time interval of the first maxTimeSamples

        @param datumOffset: meters above the sensor for datum 0 level
        @param stddev: standard deviation of tidal measurements
        @param timeFormat: strftime \% format string
        @param interp: turn on or off (True or False) interpolation
        @param verbose: send error handling reports to stderr
        '''

        global options

        if options.debug > 0:
            print '''DEBUG:
    Interpolator
      tdStart %s
      tdInterval %s ''' % (self.dtStart,self.dtInterval)

        # initialize consequetive errors counter and variables
        conseqErrs = 0
        thisdTime = lastdTime = None
        WL = lastWL = None

        # initialization of variables
        tolerance =.1 # tolerance to variability in fraction of avg tdiff
        dtDiff = None
        tdAvgInt = self.dtInterval
        tdMaxInt = datetime.timedelta(seconds=(tdAvgInt.seconds*(1+tolerance)))

        # the big loop through the data
        for line in inF:
            line.strip()

            if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue # not a data record line

            lastdTime = thisdTime
            lastWL = WL

            # the time is in a datetime.datetime object
            (thisdTime,WL,otherFields) = \
                findTideFields(line,options.timeFormat)

            if lastdTime != None:
                dtDiff = thisdTime - lastdTime

            if options.interval != None:
                # interval specified on command line (must be less than)
                # the calculated interval
                (hStr,mStr,sStr) = string.split(options.interval, sep=':')
                hInt = int(hStr)
                mInt = int(mStr)
                sFloat = float(sStr)
                sInt = int(sFloat)
                msInt = int( (sFloat - sInt) * 1000)

                optionsInterval = datetime.timedelta(hours=hInt,
                                                     minutes=mInt,
                                                     seconds=sInt,
                                                     microseconds= msInt)
                if optionsInterval < tdAvgInt:
                    tdAvgInt = optionsInterval

                tdMaxInt = datetime.timedelta(seconds=tdAvgInt.seconds *
                                              (1 + tolerance))
                if tdMaxInt.seconds <= tdAvgInt.seconds:
                    # make it at least one second more
                    tdMaxInt = datetime.timedelta(seconds=(tdAvgInt.seconds + 1))
                if options.verbose:
                    sys.stderr.write("Using interval: %d seconds; trigger interpolation %d seconds\n" %
                                     (tdAvgInt.seconds,tdMaxInt.seconds))

            if lastWL != None:
                WLdiff = float(WL) - float(lastWL)
            else:
                WLdiff = 0

            # do we have missing data ???? (dtDiff is differance between current
            # data time and previous  -- INTERPOLATION ROUTINE
            if  dtDiff != None and dtDiff > tdMaxInt:

                missingTs = int(dtDiff.seconds / tdAvgInt.seconds)

                if ((lastWL != None) and (lastdTime != None)) :
                    if options.reportFile != None:
                        reportF.write(
                            "%d missing data points from %s to %s\n" %
                            (missingTs,
                             lastdTime.strftime(timeFmts[options.timeFormat]),
                             thisdTime.strftime(timeFmts[options.timeFormat])))

                    # calculate WLstep
                    WLstep = WLdiff / float(missingTs)

                    # starting point
                    interpDT = lastdTime
                    interpWL = lastWL

                    # step through the interpolated points
                    while(True):
                        # calculate the new time
                        interpDT = interpDT + tdAvgInt
                        # calculate the new WL
                        interpWL = interpWL + WLstep

                        if interpDT >= thisdTime:
                            if options.debug > 0:
                                print "breaking ",interpDT
                            break
                        else:
                            # print the results
                            if options.debug > 0:
                                print "filing ", interpDT
                            tideOutput(outfile,
                                   options.timeFormat,
                                   interpDT,
                                   interpWL)

            # continue with uninterpolated data output
                            if options.debug > 0:
                                print "normal", thisdTime
            tideOutput(outfile,
                       options.timeFormat,
                       thisdTime,
                       WL)


class Downsampler():

    import time
    import datetime
    import string
    import numpy as np


    def __init__(self,
                 iTformat='caris',
                 oTformat='caris',
                 dtStart=datetime.timedelta(seconds=0),
                 dtInterval=datetime.timedelta(seconds=3600)):
        self.iTformat = iTformat
        self.oTformat = oTformat
        self.dtStart = dtStart
        self.dtInterval = dtInterval

        # build list of output times over a day
        intervalSecs = dtInterval.seconds
        outTime = dtStart
        self.outTimeList = [outTime]
        endTime = datetime.timedelta(days=1) + dtStart - dtInterval
        while (outTime < endTime):
            outTime = outTime + datetime.timedelta(seconds=intervalSecs)
            self.outTimeList.append(outTime)
        self.outTimeList = map(self.dayTimeLimit,self.outTimeList) # fill in begining
        self.outTimeList.sort() # in order

        if options.debug > 0:
            for timeMark in self.outTimeList:
                print timeMark

        self.halfTinterval = datetime.timedelta(seconds = (intervalSecs / 2.0))
        self.startTD = None

        # the data and time sample window
        self.reset()
        self.current = np.array([]) # row: DTtime, epochTime, value

    def dayTimeLimit(self,td):
        ''' used to reposition any datetime.timedeltas > 1 day, to
        the begining of the day'''

        oneDay = datetime.timedelta(days=1)

        if(td > oneDay):
            return (td - oneDay)
        else:
            return (td)


    def process(self,infile,outfile):
        '''
        process the input and print out the interpolate
        data based on the time interval of the first maxTimeSamples
        '''

        global options

        if options.debug > 0:
            print '''DEBUG:
    Downsampler
      dtStart %s
      dtInterval %s ''' % (self.dtStart,self.dtInterval)
        lastOutputDT = None # used to keep track of what's been done

        # the big loop through the data
        for line in inF:
            line.strip()

            if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue # not a data record line

            (dt,value,otherFields) = findTideFields(line,self.iTformat)
            if self.dtStart == None:
                # start timedate is set to begining of first day of data
                self.startTD = datetime.datetime(year=dt.year,
                                                 month=dt.month,
                                                 day=dt.day)
            epochtime = datetime2epoch(dt)
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

        # combine time.date ..
        outputDate = datetime.datetime(year=dt.year,
                                       month=dt.month,
                                       day= dt.day)
        # .. with the previous outTimeList entry
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
        elif(options.lsa): # use least squares intersection with time
            (m,b) = np.polyfit(times,values,1) # linear fit
            epochT = datetime2epoch(time)
            value = m * epochT + b
        else: # use simple average
            value = np.average(values)
        return(time,value)

    def reset(self):
        '''
        clears the window of data
        '''
        self.window = np.array([])


if __name__ == '__main__':
    main()

