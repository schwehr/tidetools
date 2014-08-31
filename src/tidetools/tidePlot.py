#!/usr/bin/env python


# subversion commands:
# svn propset svn:keywords 'Revision Date' template.py
# svn propset svn:executable ON template.py

__author__    = 'Ben Smith'
__version__   = '$Revision: 4799 $'.split()[1]
__revision__  = __version__ # For pylint
__date__ = '$Date: 2006-09-25 11:09:02 -0400 (Mon, 25 Sep 2006) $'.split()[1]
__copyright__ = '2008'
__license__   = 'GPL v3'
__contact__   = 'ben at ccom.unh.edu'
__deprecated__ = ''

__doc__ ='''
A program to plot tide files of the format <timedate>\t<depth>

Kurt Schwerh & Ben Smith - Center for Coastal and Ocean Mapping 2008,2009
http://vislab-ccom.unh.edu

@requires: U{Python<http://python.org/>} >= 2.5
@requires: U{epydoc<http://epydoc.sourceforge.net/>} >= 3.0.1
@requires: U{psycopg2<http://initd.org/projects/psycopg2/>} >= 2.0.6

@undocumented: __doc__
@since: 2008-Feb-09
@status: under development
@organization: U{CCOM<http://ccom.unh.edu/>} 

@todo: 

@see: U{python idioms<http://jaynes.colorado.edu/PythonIdioms.html>} - Read this before modifying any code here.
@see: U{Python Tips, Tricks, and Hacks<http://www.siafoo.net/article/52}
'''

# Optional...
# @author: U{'''+__author__+'''<http://vislab-ccom.unh.edu/>} FIX: replace with your name/url


import sys
import os
import time
import datetime
import exceptions # For KeyboardInterupt pychecker complaint
import traceback
from optparse import OptionParser
from string import *
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

#### local lib
from tideLib import *

##################################

def CommandLine():
    """Process the command line options"""

    global options,args

    global configFile, inputFile, outputFile, outputFileType

    global inputFiles
    
    inputFiles = []


    # get command line options

    parser = OptionParser(usage="%prog [options] tide files",
                          version="%prog "+__version__+' ('+__date__+')')


    parser.add_option('-i', '--input'
                      ,dest='inputFiles'
                      ,action='append'
                      ,type='string'
                      ,default=None
                      ,help='the name of the file to be plotted')

    parser.add_option('-v', '--verbose'
                      ,dest='verbose', default=False, action='store_true'
                      ,help='run the tests run in verbose mode')


    parser.add_option('-f','--format-time'
                      ,dest='timeFormat'
                      ,type='choice'
                      ,default='caris'
                      ,choices=timeTypes
                      ,help= 'One of ' + \
                          ', '.join(timeTypes)+ ' [default: %default] ')
        
    (options,args) = parser.parse_args()

    # use command line arguments as input file list
    
    inputFiles += args
    if options.inputFiles != None:
        inputFiles += options.inputFiles


##########################################

def main():
    '''
    The main routine.
    '''

    global options,args,extRE
    global inputFiles

    CommandLine()

    # set up plot
    fig = plt.figure()
    ax = fig.add_subplot(111)
    nColors = len(plotColors)
    colIndx = 0
#    dtList= []

    for filename in inputFiles:

        (times,data,otherFields) = readTideFileToLists(filename=filename
                                ,timeFormat = options.timeFormat)
        
        ax.plot(times,data,'.-',
                color=plotColors[colIndx],
                label="%s (%d points)" % (filename,len(data)))
        # add the the datetimes to the dtList
#        dtList = np.union1d(dtList,times)

        colIndx = (colIndx + 1) % nColors

    # finish up formating the plot
    fig.autofmt_xdate()
    plt.legend()
    plt.show()



######################################################################
# Code that runs when this file is executed directly
######################################################################
if __name__ == '__main__':
    main()

