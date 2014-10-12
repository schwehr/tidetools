#!/usr/bin/env python
'''
__author__    = 'Ben Smith'
__version__   = '$Revision: 9665 $'.split()[1]
__revision__  = __version__ # For pylint
__date__ = '$Date: 2008-06-19 08:23:00 -0700 (Thu, 19 Jun 2008) $'.split()[1]
__copyright__ = '2008'
__license__   = 'Apache 2.0'
__contact__   = 'ben at ccom.unh.edu'
__doc__ ='''


################# Libs
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
    p.add_option("-I","--InputFormat",
                 type="choice",
                 dest="inputFormat",
                 default="SI",
                 choices=["SI","CM"],
                 help="One of these: SI (Star Island), CM (Castine, Maine)")
    p.add_option("-o", "--outputFile", 
                 default = None,
                 type="string", dest="outputFile",
                 help="the file to write to (overwrites)",
                 metavar="FILE")
    p.add_option("-T", "--Tinterval", type="string", 
                 default=None,
                 dest="interval",
                 help='''HH:MM:SS for upsampling interval. tideInterp
can be used to artificial increase the density of the data.''')
    p.add_option("-R", "--Report",default=None,type="string",dest="reportFile",
                 help='''filename for report on points inserted into data.''',
                 metavar="FILE")
    p.add_option("-X", "--debug", type="int", default=0,
                 dest="debug",
                 help="debug level: 0 is off; powers of 2 for levels")
    p.add_option("-v", "--verbose", action="store_true", default=False,
                 dest="verbose",
                 help="")
    p.add_option('-f','--timeFormat'
                      ,dest='timeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
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

    global inF, outF , errF , reportF

    
    errF = sys.stderr

    itr = Interpolator()
    p = CommandLine()

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

    for file in filelist:
        inF = open(file,"r")
        itr.process(inF,outF) # process the file
        inF.close()

    outF.close()



class Interpolator():

    global options
    
    ##################################################################
    def sample(self):
        ''' samples the time differences to find an mode of time diff '''

        maxSamples = 500 # for determining a true avgTinterval
        thisdTime = lastdTime = None
        samples = {}
        sampleCounter = 0

        inF.seek(0) # start at begining of file

        for line in inF:
            line.strip()
        
            if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue # not a data record line

            lastdTime = thisdTime 

            # the time is in a datetime.datetime object
            (thisdTime,WL,otherFields) = \
                findTideFields(line,options.timeFormat)

            
            sampleCounter += 1
            if lastdTime != None:
                diff = (thisdTime - lastdTime).seconds
                if samples.has_key(diff):
                    # exists so increment
                    samples[diff] += 1
                else:
                    # doesn't yet exist, initialize
                    samples[diff] = 1

            if sampleCounter >= maxSamples:
                break

        # we have our sample.. find smallest mode and rewind file
        
        keyValues = samples.keys()
        keyValues.sort()
        keyValues.reverse() # so that the last value looked at is the smallest

        maxCount = 0
        modal = 0
        for key in keyValues:
            if samples[key] > maxCount:
                modal = key
                maxCount = samples[key]

        inF.seek(0) # rewind
        return(datetime.timedelta(seconds=modal))

    ###################################################################
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

        # initialize consequetive errors counter and variables
        conseqErrs = 0
        thisdTime = lastdTime = None
        WL = lastWL = None

        # initialization of variables
        errCount = 0
        prevTimestamp = None
        intervalAccum = datetime.timedelta(seconds=0) # initialstate
        timestampCntr = 0
        avgTinterval = 12.0 # default
        tolerance =.1 # tolerance to variability in fraction of avg tdiff
        tdAvgInt = datetime.timedelta(seconds=avgTinterval)
        tdMaxInt = datetime.timedelta(seconds=(avgTinterval*(1+tolerance)))
        dtDiff = None

        tdAvgInt = self.sample()

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



######################################################################
# Code that runs when this file is executed directly
######################################################################
if __name__ == '__main__':
    main()

