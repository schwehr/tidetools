#!/usr/bin/env python


# subversion commands:
# svn propset svn:keywords 'Revision Date' template.py
# svn propset svn:executable ON template.py

__author__    = 'Ben Smith'
__version__   = '$Revision: 100 $'.split()[1]
__revision__  = __version__ # For pylint
__date__ = '$Date: 2006-09-25 11:09:02 -0400 (Mon, 25 Sep 2006) $'.split()[1]
__copyright__ = '2009'
__license__   = 'Apache 2.0'
__contact__   = 'ben at ccom.unh.edu'
__deprecated__ = ''

__doc__ ='''
A set of utilities for smoothing time-based data, in particular
tidal data. It may also be used for filtering any vector that
does not have a time component associated.

The data may be of any size, but must be greater than twice the filter width.
The output is clipped at either end of the data set by 1/2 the filter width.

Ben Smith - Center for Coastal and Ocean Mapping 2008,2009
http://ccom.unh.edu

@requires: U{Python<http://python.org/>} >= 2.5
@requires: U{epydoc<http://epydoc.sourceforge.net/>} >= 3.0.1
@requires: U{psycopg2<http://initd.org/projects/psycopg2/>} >= 2.0.6

@undocumented: __doc__
@since: 2009-Jan-25
@status: under development
@organization: U{CCOM<http://ccom.unh.edu/>} 

@see: U{python idioms<http://jaynes.colorado.edu/PythonIdioms.html>} - Read this before modifying any code here.
@see: U{Python Tips, Tricks, and Hacks<http://www.siafoo.net/article/52}
'''

# Optional...
# @author: U{'''+__author__+'''<http://vislab-ccom.unh.edu/>} FIX: replace with your name/url


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

## local import
from tideLib import *


########### globals #############

defInputFile = None
defOutputFile = None
defFilterSpec = [10,10,10,10,10,10,10,10] # 15 wide boxcar
#defFilterSpec = [10,10,9,9,9,9,9,8,8,8,8,7,7,7,6,5,4,3,3,2,2,1,1] # 45-wide
#defFilterSpec = [10,7,5,4,3,2,1] # 13 wide 'Gaussian' (sort of)
'''
FilterSpec represents a symetrical filter centered around the first element
'''
defTimeColumn = 1
defDataColumn = 2
defThreshold = None
defVerbose = False
defDebug = 0 # binary masks are applied: i.e., 0,1,2,4,8,16

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
    p.add_option("-F", "--filterSpec", default = None,
                 type="string", dest="filterSpecStr",
                 help='''a string of space delimited numbers that describe
the filter weights. The filter created will be symetrical around the first
element in the list and as wide as twice the description minus 1''')
    p.add_option("-W","--widthBoxcar", type="int", default=None,
                 dest="boxcarWidth",
                 help='''width of a boxcar filter. 
Use of this option supercedes the -F --filterSpec option''')
    p.add_option("-t", "--timeCol", type="int", default=defTimeColumn,
                 dest="timeColumn",
                 help="The input column representing time")
    p.add_option("-d", "--dataColumn", type="int", default=defDataColumn,
                 dest="dataColumn",
                 help="The input column with the data to be filtered")
    p.add_option("-T", "--threshold", type="int", default=None,
                 dest="threshold",
                 help='''minimum change required to trigger smoothing. 
This is used to prevent jitter.''')
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
    p.add_option("--FieldSeperator", default = '\t',
                 type="string", dest="fieldSep",
                 help="the character(s) used to separate fields in the output; [default '\t']")
    p.add_option("--RecordSeperator", default = '\n',
                 type="string", dest="recSep",
                 help="the character(s) used to separate records in the output; [default '\n']")
        
        
        

    (options,args) = p.parse_args()

    ### a few adjustments 
    if options.threshold != None:
        # insure we don't have neg. val
        options.threshold = abs(options.threshold) 

    return(p)

######################### main ##########################################

def main():

    global options, args
    global inF, outF , errF

    
    p = CommandLine()

    # define the filter spec

    if options.boxcarWidth != None:
        filterSpec = [10] * ((options.boxcarWidth / 2) + 1 )
    elif options.filterSpecStr:
        strings = split(options.filterSpecStr)
        filterSpec = map(lambda s: int(s),strings)
    else: # not specified on command line, use default
        filterSpec = defFilterSpec

    # define the filter
    filter = LowPass(options.threshold,filterSpec)

    # open input and output and err
    if(options.input != None): 
        inF = open(options.input,"r")
    else:
        inF = sys.stdin

    if(options.output != None):
        outF = open(options.output,"w")
    else:
        outF = sys.stdout

    errF = sys.stderr
    timeIdx = options.timeColumn - 1
    dataIdx = options.dataColumn - 1

    # the big loop through the data
    for line in inF:
        line.strip()
        
        # the time is in a datetime.datetime object
        (time,data,otherFields) = findTideFields(line,
                                                 options.timeFormat,
                                                 options.fieldSep,
                                                 options.recSep)

        # now we can apply the smoothing
        (thisTime,thisData) = filter.smooth(time,data)

        if (thisData != None and thisTime != None):
            # substitute back into the other fields
            fieldStrs = [thisTime, thisData] + otherFields

            if options.debug & 4:
                errF.write("output " +str(fieldStrs)+"\n")

            tideOutput(outF,
                       timeFormat=options.timeFormat,
                       dTime=thisTime,
                       waterlevel=thisData,
                       fieldSep=options.fieldSep,
                       recSep=options.recSep)

            # else skip the line in output.. hopefully only because
            # we are at the begining or end of the data set


################### LowPass ############################################

class LowPass():
    '''
    The filter uses a two lists that are aligned. One lists
    contains the weighting factors (fractions). The other list
    is the queue of data as it moves through the evaluation process.
    Once the data list is filled, the filter is applied to generate
    the center value, which is then output. The weights are assigned
    to their positions when the LowPass is first created.



    Example:                
      filterSpec = [9,5,1]  
      design = [1,5,9,5,1]  
      design.sum = 21
      weights = each design element divided by 21 (sum)
      weights = [0.048,0.238,0.429,0.238,0.048]

    Now, if the data list is filled, these weights are applied
    to find the center value. 

    Example 1:
      datalist = [100,    105,    109,     100,    110    ]
      weights =  [  0.048,  0.238,  0.429,   0.238,  0.048]
      products = [  4.8,   25.0    46.7,    23.8,    4.76 ]
      sum of products = 105 which is the output value.
      
    Example 2 (with the same filter design, i.e., weights).
    The data list has shifted to the next window position. 
    The leftmost element is shifted off. The new value is
    1030, a real spike. this new value is going effect the
    value that is now at the middle of the window.
      datalist = [105,     109,      100,    110,   1030]
      weights =  [  0.048,   0.238,    0.429,  0.238,  0.048]
      products = [  5.00,   25.9,     42.9,   26.2,   49.0]
      sum (and new value for 100 ) = 150

    Because of the nature of this little filter design (1,5,9,5,1),
    the closer the spike is to the center value, the greater the weight
    applied, and the greater the influence on the data. 

      '''
    
    global inF, outF, errF

    errF = sys.stderr

    def __init__(self,threshold,filterSpec):
        self.threshold(threshold)
        self.weights(filterSpec)
        self.center = len(filterSpec) - 1

    ###
    def threshold(self,threshold=None):
        if threshold != None:
            self.threshold = threshold
        return threshold

    ###
    def weights(self,filterSpec=None):

        global errF

        if filterSpec != None:
            
            # form the weighting list, the sum of which must be 1


            #    an example filterSpec is 9 8 5 3  
            # grab the first element  
            centerVal = filterSpec.pop(0)  # 9   --pop(0) is eqivalent to shift
            revList = list(filterSpec)        # 8 5 3 -- need to make a copy
            revList.reverse()           # 3 5 8 
            designList = revList + [centerVal] + filterSpec # 3 5 8 9 8 5 3
            if options.debug & 1:
                errF.write("design " + str(designList)+"\n")
        
            total = sum(designList)
    
            self.weights = map((lambda x: float(x) / float(total)), designList)
            self.listLen = len(self.weights)
            self.dataList = []
            if options.debug & 8:
                errF.write("weights " + str(self.weights)+"\n")
        return self.weights

    ###
    def push(self,value,time):
        '''
        push a new value on the list representing the current
        data window
        '''

        self.dataList.append([value,time]) # each element is a list of two  
        # drop a value from the other end to keep the list 
        # the same size
        if len(self.dataList) > self.listLen:
            self.dataList.pop(0) # equivalent to shift, remove front element

        if options.debug & 16:
            errF.write(str(self.dataList)+"\n")



    ###
    def pop(self):
        '''
        get the last value pushed
        '''
        return self.dataList.pop()



    ###
    def dataSet(self,pos):
        '''
        returns the tuple at the position pointed to
        '''
        return self.dataList[pos]

    ###
    def value(self,pos,val=None):
        '''
        sets the value at position indicated, if value is given.
        Always returns the value at that position
        '''
        if val != None:
            self.dataList[pos][0] = val
        return self.dataList[pos][0]

    ###
    def time(self,pos,time=None):
        '''
        sets the time at position indicated, if time is given.
        Always returns the time at that position
        '''
        if time != None:
            self.dataList[pos][1] = time
        return self.dataList[pos][1]

    ###
    def weight(self,pos):
        '''
        returns the weight at position indicated
        '''
        return self.weights[pos]

    ###
    def avg(self):
        '''
        returns the sum of the product of weights and data values
        '''
        sum = 0.00
        for n in range(0,self.listLen):
            if options.debug & 8:
                errF.write("(%f * %f = %f)\n" % ( self.weights[n],
                                                   self.dataList[n][0],
                                                   self.weights[n] * \
                                                       self.dataList[n][0]))
            sum += self.weights[n] * self.dataList[n][0]
        
        if options.debug & 8:
            errF.write("SUM %f\n\n" % sum)
        return sum

    ###
    def smooth(self,time,value):
        '''
        push new value into window list, dropping the oldest value,
        and returning the middle data set.
        '''

        self.push(value,time)

        # apply threshold filter
        if((self.threshold != None) and ( len(self.dataList) > 3)):
            nearAvg = (self.value(-3) + self.value(-1))/2.0
            # replace previous value with nearAvg
            self.value(-2,nearAvg)

        # the real filter
        if(len(self.dataList) == self.listLen): # the data window is full
            result = [self.dataList[self.center][1],self.avg()]
        else:
            result = [None,None]

        return result

        


#########################################################################
if __name__=='__main__':
    main()
