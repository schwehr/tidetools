#!/usr/bin/env python
"""Plot tide files of the format <timedate>\t<depth>."""

import sys
import os
import time
import datetime
import exceptions # For KeyboardInterupt pychecker complaint
import traceback
from optparse import OptionParser
from string import *  # TODO: Do not import *.
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from tideLib import *  # TODO: Do not import *.
from __init__ import __version__


def CommandLine():
    """Process the command line options"""

    global options,args

    global configFile, inputFile, outputFile, outputFileType

    global inputFiles

    inputFiles = []


    # get command line options

    parser = OptionParser(usage="%prog [options] tide files",
                          version="%prog "+__version__)


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


def main():
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
        # dtList = np.union1d(dtList,times)

        colIndx = (colIndx + 1) % nColors

    # finish up formating the plot
    fig.autofmt_xdate()
    plt.legend()
    plt.show()


if __name__ == '__main__':
    main()

