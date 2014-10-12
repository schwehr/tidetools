#!/usr/bin/env python
"""Process the data for from Aanderaa data logger to Caris format.

Comes in this format on tide2.schwehr.org
in ~data/data/tide/tide-memma-2008-MM-DD

# START LOGGING UTC seconds since the epoch: 1213488002.45
# SPEED:       9600
# PORT:        /dev/ttyS0
# TIMEOUT:     300.0
# STATIONID:   memma
# DAEMON MODE: True
635  711  427,rmemma,1213488014.57
635  711  427,rmemma,1213488026.7
635  711  427,rmemma,1213488038.83
635  712  427,rmemma,1213488050.95
635  712  426,rmemma,1213488063.08
635  712  426,rmemma,1213488075.21
635  712  426,rmemma,1213488087.33
63

Caris seems to want:

----------- FORT POINT , NH:  8423898 -----------
--------------------- 8423898.tid ---------------------
--------------------- Time Zone:  UTC  ---------------------

--------------------- Invariant Fields ---------------------
Name             Type Size    Units Value
------------------------------------------------------------
station_id       CHAR    8     8423898
station_name     CHAR    15    FORT POINT , NH
data_product     CHAR    10   UNVERIFIED
start_time       INTG    4   seconds 2007/06/01 00:00:00
end_time         INTG    4   seconds 2007/06/11 19:30:00
file_date        INTG    4   seconds 2007/06/11 20:10:53
max_water_level  REAL    4   metres 03.21
min_water_level  REAL    4   metres -00.31
------------------------------------------------------------

---------------------- Variant Fields ----------------------
Name             Type Size    Units
------------------------------------------------------------
time             INTG    4   seconds
water_level      REAL    4   metres
std_dev          REAL    4   metres
------------------------------------------------------------

2007/06/01 00:00:00    1.18   0.008
2007/06/01 00:06:00    1.23   0.007
2007/06/01 00:12:00    1.28   0.007
2007/06/01 00:18:00    1.34   0.009
2007/06/01 00:24:00    1.41   0.009
2007/06/01 00:30:00    1.48   0.009
2007/06/01 00:36:00    1.55   0.010
2007/06/01 00:42:00    1.62   0.008

see: http://pypi.python.org/pypi/tappy/ Is tappy useful?

2010/07/22: adding a comma delimited format for microwave tide station:
<mm/dd/yyy>,<hh:mm:ss>,<id>,<height(float)>,<unit(str)>,<method(str)
"""

from optparse import OptionParser
import time
import datetime
import string
import os
import re
import sys
import numpy as np

from __init__ import __version__
import tideLib

# Coefficients for water level in meters.  This is specific to each 
# pressure sensor.
A = -1.008E-01
B = 5.125E-03
C = 7.402E-08

# input formats
snttRE = re.compile(r'^\s*(\d+)\s+(\d+)\s+(\d+),(\w+),(\d+\.\d+)')
dttnRE = re.compile(r'^\s*(\d+\/\d+\/\d+\s+\d+:\d+)\s+(\d+)\s+(-?\d+\.\d+)')
tvwlRE = re.compile(r'(\d+:\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)')
cdlRE = re.compile(r'^\s*(\d+\/\d+\/\d+),(\d+:\d+:\d+),\S*,(\d+\.\d+)')
#Time/Date :   8 July-2009 16:53:00
dateStrRE = re.compile(r'Time/Date\s+\:\s+(\d+)\s+(\w+-\d+)')


def snttParser(line,D=None):
    '''
    input line like:
      stID prss temp sta   EpochTime
      635  800  325,rmemma,1210269868.43
    parses input line to generate datetime, pressure, temperature tuple
    '''

    global options

    try:
        result = snttRE.search(line)
        # (stationId,N,rawTemp,station,timestamp)
        fields = result.groups()
        N = float(fields[1])
        rawTemp = float(fields[2])
        timestamp = float(fields[4])
        DT =  datetime.datetime.utcfromtimestamp(timestamp)

        # water Level(m)=((A+BN+CN^2+DN^3)/d*g)) with D = 0.0
        WL = ( A + B*N + C*(N**2) ) - options.datumOffset

    except:
        return(None,None)

    return(DT,WL)

def dttnParser(line,D=None):
    '''
    input line like:
      time      temp     waterlevel
      16:53     377.0    576.0
    parses input line to generate datetime, pressure, temperature tuple
    '''

    global options

    try:
        result = dttnRE.search(line)
        # (timeStr,rawTemp,N)
        fields = result.groups()
        rawTemp = float(fields[1])
        WL = float(fields[2])
        DT = datetime.datetime.strptime(fields[0],'%Y/%m/%d %H:%M')
    except:
        return(None,None)

    return(DT,WL)

def cdlParser(line,D=None):
    '''
    input line like:
    06/30/2010,15:39:28,h-3611,2.458,m,G

    and picking off the date-time string and height
    '''
    global options

    try:
        result = cdlRE.search(line)
        fields = result.groups()
        DTstr = '%s %s' % (fields[0],fields[1])
        WL = float(fields[2])
        DT = datetime.datetime.strptime(DTstr,'%m/%d/%Y %H:%M:%S')
    except:
        return(None,None)

    return(DT,WL)

def tvwlParser(line,D=None):
    '''
    input line like:
      time      voltage temp     waterlevel
      16:53     10.2    377.0    576.0
    with each day's data starting with a line like:
      Time/Date :   8 July-2009 16:53:00

    parse input line to generate datetime, pressure, temperature tuple
    '''
    global options

    try:
        result = tvwlRE.search(line)
        # (timeStr,rawTemp,N)
        fields = result.groups()
        rawTemp = float(fields[3])
        WL = float(fields[2])
        (H,M)= string.split(fields[0],':')
        T = datetime.timedelta(hours = int(H), minutes = int(M))
        DT = D + T
    except:
        return(None,None)

    return(DT,WL)

inputParser = {
    'SNTT' : snttParser,
    'DTWL' : dttnParser,
    'TVWL' : tvwlParser,
    'CDL'  : cdlParser
}


def CommandLine():
    '''
    Process the command line options and arguments
    '''
    global options,args

    p = OptionParser(usage="%prog [options] tide files",
                          version="%prog "+__version__)
    p.add_option('-i','--input-files',
                 dest='inputFiles',
                 action='append',
                 default=[],
                 help='What files to read from ' + \
                 '[default: %default - stdin if None]')
    p.add_option('-I','--InputFormat'
                 ,dest='InputFormat'
                 ,type='choice'
                 ,default='SNTT'
                 ,choices=inputParser.keys()
                 ,help= 'Input time format. One of: ' + \
                 ', '.join(inputParser.keys()) +
                 ' [default: %default] ')
    p.add_option('-o','--output-file',
                 dest='outFilename', default=None,
                 help='What filename to write to [default: %default - stdout if None]')

    p.add_option('-O','--OutputFormat'
                 ,dest='timeFormat'
                 ,type='choice'
                 ,default='caris'
                 ,choices=tideLib.timeTypes
                 ,help= 'Output time format. One of: ' + \
                 ', '.join(tideLib.timeTypes)+ ' [default: %default] ')
    p.add_option('-B','--BadLineFile'
                 ,dest='badLineFile'
                 ,default=None,
                 help='Place unparseable lines in a file for review [default: None]')
    p.add_option('-t','--timeshift',
                 dest='timeshift', default=0
                 ,type='float'
                 ,help='in seconds.  You will need to ' +\
                 'shift time for data from 2008-06-15 and ' +\
                 'older by +/- 45 seconds [default: %default]')

    p.add_option('-v', '--verbose',
                 dest='verbose', default=False, action='store_true',
                 help='run the tests run in verbose mode')

    p.add_option('-D','--datum-offset'
                 ,dest='datumOffset'
                 ,type='float'
                 ,default=0
                 ,help= 'Distance from the sensor up to the '+\
                 'datum offset in meters (negative is below the '+\
                 'sensor) [default: %default] ')
    p.add_option("--FieldSeparator", default = '\t',
                 type="string", dest="fieldSep",
                 help="the character(s) used to separate fields in files; [default '\\t']")
    p.add_option("--RecordSeparator", default = '\n',
                 type="string", dest="recSep",
                 help="the character(s) used to separate records in the files; [default '\\n']")


    (options, args) = p.parse_args()

    return p


def main():
    """Process a list of files."""

    global options, args, blf
    blf = None # badLineFile filePtr

    p = CommandLine()

    out = sys.stdout
    if options.outFilename:
        out = file(options.outFilename,'w')
    if options.badLineFile != None:
        blf = file(options.badLineFile,'w')

    filelist = args + options.inputFiles

    # statistics
    everything = good = bad = 0

    for filename in filelist:
        (a,b,g) = processFile(file(filename),out)

        sys.stderr.write('%s:: all: %d :: good: %d :: bad: %d\n' %
                     (filename,a,g,b))
        everything += a
        bad += b
        good += g

    sys.stderr.write('TOTAL:: all: %d :: good: %d :: bad: %d\n' %
                     (everything, good, bad))


def processFile(infile,out):
    '''
    process a single file
    '''

    global options,blf

    # initialization of variables
    datalineCount = 0
    errCount = 0
    D = datetime.timedelta(0)

    # the big loop
    for line in infile:

        if commentRE.match(line): continue # skip comment lines

        datestrMatch = dateStrRE.search(line)

        if datestrMatch != None:
            datestr = '%s %s' % datestrMatch.groups()
            D = datetime.datetime.strptime(datestr,'%d %B-%Y')
            if options.verbose:
                sys.stderr.write('DATE LINE: '+line.strip()+' -> '+
                                 D.ctime()+'\n')

        datalineCount += 1

        (DT,WL) = inputParser[options.InputFormat](line,D)

        if(DT == None or WL == None):
            if options.badLineFile != None:
                blf.write(line)
            if options.verbose:
                sys.stderr.write('bad line: '+line.strip()+'\n')
            errCount += 1
            continue

        if options.timeshift != 0: # shift if specified
            DT = DT + datetime.timedelta(seconds=options.timeshift)
            print DT
        tideOutput(out,
                   timeFormat=options.timeFormat,
                   dTime=DT,
                   waterlevel=WL,
                   fieldSep=options.fieldSep,
                   recSep=options.recSep)

    return(datalineCount,errCount,datalineCount-errCount)


if __name__ == '__main__':
    main()


