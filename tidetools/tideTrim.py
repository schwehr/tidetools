#!/usr/bin/env python
"""Trim tide data to a window of time, and or statistical window."""

import sys
import os
import string
import time
import datetime

import exceptions # For KeyboardInterupt pychecker complaint
import traceback


from optparse import OptionParser
from string import *
from random import *
import re

from numpy import *

## local import
from tideLib import *


########### globals #############

defInputFile = None
defOutputFile = None
defVerbose = False
defDebug = 0 # binary masks are applied: i.e., 0,1,2,4,8,16

cmdLineDTformat = '%Y/%m/%d-%H:%M:%S'

def CommandLine():
    '''
    Process the command line options and arguments
    '''
    global options,args

    p = OptionParser()
    p.add_option("-i", "--inputFile", default = defInputFile,
                 type="string", dest="input",
                 help="the file to read",
                 metavar="FILE")
    p.add_option("-o", "--outputFile", default = defOutputFile,
                 type="string", dest="output",
                 help="the file to write to (overwrites)",
                 metavar="FILE")

    p.add_option("-b", "--beginTime", default = None,
                 type="string", dest="beginTime",
                 help='''a string describing a time date. The format
is %Y/%m/%d-%H:%M:%S''')
    p.add_option("-e", "--endTime", default = None,
                 type="string", dest="endTime",
                 help='''a string describing a time date. The format
is %Y/%m/%d-%H:%M:%S''')
    p.add_option("-s", "--sigmas", type="float", default=1.5,
                 dest="sigmas",
                 help='''values represent sigma (std deviation) of the last
width (see -w --width), default is 1.5 sigma''')
    p.add_option("-w", "--width", type="int", default=13,
                 dest="width",
                 help='''width of historic samples used to find standard deviation width''')
    p.add_option("-l", "--LSR", action="store_true", default=True,
                 dest="LSR",
                 help="Least Squares Linear Regression based statistics")
    p.add_option("-n", "--noLSR", action="store_false", default=True,
                 dest="LSR",
                 help="no LSR - use simple statistics")
    p.add_option('-B','--BadDataFile'
                 ,dest='badDataFile'
                 ,default=None,
                 help='Place out-of-bounds data in a file for review [default: None]')
    p.add_option("-X", "--debug", type="int", default=0,
                 dest="debug",
                 help="debug level: 0 is off; powers of 2 for levels")
    p.add_option("-v", "--verbose", action="store_true", default=defVerbose,
                 dest="verbose",
                 help="")
    p.add_option('-f','--timeFormat'
                      ,dest='timeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
    p.add_option("--FieldSeparator", default = '\t',
                 type="string", dest="fieldSep",
                 help="the character(s) used to separate fields in the output; [default '\\t']")
    p.add_option("--RecordSeparator", default = '\n',
                 type="string", dest="recSep",
                 help="the character(s) used to separate records in the output; [default '\\n']")



    (options,args) = p.parse_args()

    return(p)


def main():

    global options, args
    global inF, outF , errF

    goodCntr = 0
    badCntr = 0

    beginDT = None
    endDT = None

    p = CommandLine()

    if(options.beginTime != None):
        beginDT = datetime.datetime.strptime(options.beginTime,cmdLineDTformat)
    if(options.endTime != None):
        endDT = datetime.datetime.strptime(options.endTime,cmdLineDTformat)

    # create the Trim object
    trim = Trim(beginDT,
                endDT,
                options.sigmas,
                options.width)

    # open input and output and err
    if(options.input != None):
        inF = open(options.input,"r")
    else:
        inF = sys.stdin

    if(options.output != None):
        outF = open(options.output,"w")
    else:
        outF = sys.stdout

    if options.badDataFile != None:
        bdf = file(options.badDataFile,'w')



    # the big loop through the data
    for line in inF:
        line.strip()

        # the time is in a datetime.datetime object
        (time,data,otherFields) = findTideFields(line,
                                                 options.timeFormat,
                                                 options.fieldSep,
                                                 options.recSep)

        (oTime,oData) = trim.test(time,data)
        if(oTime != None) and (oData != None):
            tideOutput(outF,
                       timeFormat=options.timeFormat,
                       dTime=oTime,
                       waterlevel=oData,
                       fieldSep=options.fieldSep,
                       recSep=options.recSep)
            goodCntr += 1
        else:         # else skip the line in output
            badCntr += 1
            if options.badDataFile != None:
                bdf.write(line)

    inF.close()
    outF.close()
    if options.verbose:
        sys.stderr.write("%d good records; %d bad records\n" % (goodCntr,badCntr))



class Trim():

    def __init__(self,beginT=None,endT=None,sigmas=1,width=None):
        self.beginT = beginT
        self.endT = endT
        self.sigmas = sigmas
        self.queue = empty((0,2)) # empty array, two columns
        if width != None:
            if (width % 2) == 0:
                # can only be an odd number
                self.width = width + 1
            else:
                self.width = width
        self.center = self.width / 2


############
    def test(self,time,data):
        '''
        returns True or False depending on whether the data and time
        are within the constraints of the Trim object
        '''

        # the time constraints
        if ( (self.beginT != None) and (time < self.beginT)):
            return [None,None]
        if ( (self.endT != None) and ( self.endT < time)):
            return [None,None]


        # a outlier filter is specified: use it
        if (options.LSR):

            self.queue = vstack((self.queue,[time,data])) # push

            # we have a full queue - let's use it
            if len(self.queue) > self.width:
                # first, let's drop the earliest member of the queue
                self.queue = self.queue[1:,:] # equivalent to a shift
                # now do the stats
                if (self.LSLRstdevEval()):
                    return self.queue[self.center]
                else:
                    return [None,None]

        return ([time,data])

#############
    def stdevEval(self):
        '''
        compares center element height to the standard deviation
        from the mean of the height queue.
        If the center value is outside sigmas from mean, returns False,
        else returns True
        '''

        times = []
        for td in self.queue[:,0]:
            # using epoch seconds
            times.append(time.mktime(td.timetuple()))

        times = self.queue[:,0]
        vals = self.queue[:,1] # second column
        mean = vals.mean()
        stdev = vals.std()
        diff = abs(mean,vals[center])
        if (diff < (sigmas * stdev)):
            return True
        else:
            return False

    def LSLRstdevEval(self):
        '''
        applies the stdevEval to least squares
        linear regression for the points in the
        queue
        '''

        times = []
        for td in self.queue[:,0]:
            # using epoch seconds
            times.append(time.mktime(td.timetuple()))
        times = array(times)
        vals = self.queue[:,1]
        (m,b) = polyfit(times,vals,1)
        mt = times * m
        intercepts = mt + b
        diffs = vals - intercepts
        stdev = std(diffs)
        testVal = float(self.queue[self.center,1])
        testIntr = float(intercepts[self.center])
        diff = abs(testVal - testIntr)
        if (diff < (self.sigmas * stdev)):
            return True
        else:
            return False


if __name__=='__main__':
    main()
