#!/usr/bin/env python
"""TODO: Describe module."""

import time
import datetime
import os
import sys
from numpy import *
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
                      ,dest='inputFormat'
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
                      ,dest='outputFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'Output time format. One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
    p.add_option("-l", "--label",
                 default = None,
                 type="string", dest="label",
                 help="the label (station ID) to add to each output line")
    p.add_option("-w", "--window",
                 default = '01:00:00',
                 type="string", dest="windowTstr",
                 help="the time window in which to find peak values. \
The window is centered around the curve's critical points. \
Format is 'HH:MM:SS'.")
    p.add_option("-t", "--threshold", type="float", default=0.005,
                 dest="threshold",
                 help="debug level: 0 is off; powers of 2 for levels")
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
    (hStr,mStr,sStr) = options.windowTstr.split(':')
    options.window = float(60*60*int(hStr) +
                           60*int(mStr) +
                           int(sStr))

    return(p)

def main():
    global options, args
    global inF, outF , errF

    errF = sys.stderr

    p = CommandLine()

    # open output
    if(options.outputFile != None):
        outF = open(options.outputFile,"w")
    else:
        outF = sys.stdout

    pk = Peaks(output = outF,
               label = options.label,
               threshold = options.threshold,
               inputFormat = options.inputFormat,
               outputFormat = options.outputFormat,
               window = options.window)

    # process the input files
    filelist = args + options.inputFiles

    for file in filelist:
        inF = open(file,"r")
        pk.process(inF) # process the file
        inF.close()

    outF.close()


######################### class Peaks ########################

class Peaks():
    '''
    The class that provides methods for finding peaks in
    tidal data
    '''

    def __init__(self,
                 output,
                 label,
                 threshold,
                 inputFormat,
                 outputFormat,
                 window):
        self.output = output
        self.label = label
        self.threshold = threshold
        self.inputFormat = inputFormat
        self.outputFormat = outputFormat
        self.windowTwidth = window
        self.dataWindow = self.Window(self.windowTwidth)

    ######### subclass Window ####################

    class Window():
        '''Data Window with time and value and methods for manipulating
        the window.'''

        def __init__(self,width):
            self.widthDT = datetime.timedelta(seconds=width)
            self.queue = empty((0,2)) # empty array, two columns

        def push(self,time,value):
            '''
            Adds data to the window, but removes any
            data that is too old, i.e., outside of the time
            width. Returns if queue is full or not (True or False).
            '''

            full = False
            self.queue = vstack((self.queue,[time,value]))
            # delete any data that is too old, reading queue backwards
            while(len(self.queue) > 0):
                if((time - self.queue[0][0]) > self.widthDT):
                    self.queue = self.queue[1:,:] # equivalent to a shift
                    full = True
                else:
                    break
            return full

        def isCentered(self,dt):
            '''
            determines if dt (datetime) is at the center of the data window
            '''
            center = len(self.queue) / 2 # integer division will truncate
            # compare datetime at the center of the queue to the test datetime
#            print (self.queue[center][0] == dt),
#            print "critical time: ",dt,'   center',self.queue[center][0]
            return (self.queue[center][0] >= dt)

        def max(self):
            '''
            return the datetime and value with the maximum value
            in the queue.
            '''
            maxValue = -100000.0
            maxTime = None
            for entry in self.queue:
                if entry[1] > maxValue:
                    maxTime = entry[0]
                    maxValue = entry[1]
            return (maxTime,maxValue)

        def min(self):
            '''
            return the datetime and value with the minimum value
            in the queue.
            '''
            minValue = +100000.0
            minTime = None

            for entry in self.queue:
                if entry[1] < minValue:
                    minTime = entry[0]
                    minValue = entry[1]

            return (minTime,minValue)


    ############### end of Window subclass ######################

    def process(self,infile):
        '''
        Uses the change of slope sign to determine peaks. Outputs
        normal time and waterlevel along with a signal to whether it
        is a minimum (L) or maximum (H) and options stamp to indicate
        which tide station the data represents
        '''

        global options

        thisTrend = lastTrend = None
        peakType = None
        WL = lastWL = None
        thisTime = lastTime = None
        criticalDT = None

        # the big loop through the data

        for line in inF:
            line.strip()

            if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue # not a data record line

            # the time is in a datetime.datetime object
            (thisTime,WL,otherFields) = \
                findTideFields(line,self.inputFormat)

            winState = self.dataWindow.push(thisTime,WL)

            # threshold
            if lastWL != None:
                thisTrend = lastWL - WL
                if (abs(thisTrend) <= self.threshold):
                    continue

            # see if the trend has switched and which direction
            if(thisTrend > 0.0 and lastTrend < 0.0) :
                peakType = 'H'
                criticalDT = thisTime
                if options.debug > 0:
                    print "High Critical ",criticalDT, WL
            elif(thisTrend < 0.0 and lastTrend > 0.0) :
                peakType = 'L'
                criticalDT = thisTime
                if options.debug > 0:
                    print "Low Critical ",criticalDT, WL

            # if critical point is in center of window,
            #  evaluate and output
            if (criticalDT != None and
                self.dataWindow.isCentered(criticalDT)):
                if peakType == 'H':
                    (dt,value) = self.dataWindow.max()
                    tideOutput(self.output,self.outputFormat,
                        dt, value, [peakType,self.label],
                               fieldSep=options.fieldSep,
                               recSep=options.recSep)
                elif peakType == 'L':
                    (dt,value) = self.dataWindow.min()
                    tideOutput(self.output,self.outputFormat,
                        dt, value, [peakType,self.label],
                               fieldSep=options.fieldSep,
                               recSep=options.recSep)
                criticalDT = None

            lastTime = thisTime
            lastWL = WL
            lastTrend = thisTrend


if __name__ == '__main__':
    main()

