'''
Utility routines common to the tideTools
'''

import sys
import datetime
import time
import re
import string


########### globals #################

### regular expressions compiled

commentRE = re.compile(r"^\s*\#") # a comment line
blankRE = re.compile(r"^\s*$") # a blank line

### Fmts and Types

timeFmts = {
    'caris':'%Y/%m/%d %H:%M:%S'
    ,'matlab':'%Y\t%m\t%d\t%H\t%M\t%S\t'
}

timeTypes=timeFmts.keys()+['UNIXepoch']


plotColors=['blue','red','green','orange','black']

################ sampleTimedelta ###########################
def sampleTimedelta(fPtr,options):
    '''
    Reads a data file pointed to by fPtr (the file must already be open),
    and finds the lowest mode value of time deltas. Rewinds the file
    after sampling. If a maxSample is specified, then only that many 
    samples are taken, otherwise the entire file is read.

    The value returned is a datetime.timedelta value and is found by
    looking at the statistical histogram of time deltas. This method 
    does not work well if the timestamps are random or have minor variations.
    (Perhaps we will move to "Kernel Density Estimation" if such refinement
    is needed. (Thanks to BRK for that suggestion.)
    '''
    maxSamples = options.maxSamples
    timeFormat = options.timeFormat
    fieldSep = options.fieldSep
    recSep = options.recSep

    if options.debug > 0:
        print '''DEBUG:
    sampleTimedelta 
      maxSamples %d \n''' % (maxSamples)

    thisdTime = lastdTime = None
    samples = {}
    sampleCounter = 0
    diff = 0

    fPtr.seek(0) # start at begining of file

    for line in fPtr:
        line.strip()
        
        if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
            continue # not a data record line

        lastdTime = thisdTime 

        # the time is in a datetime.datetime object
        (thisdTime,WL,otherFields) = \
            findTideFields(line,timeFormat)

            
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

    if options.debug > 0:
        print '''DEBUG:
    sampleTimedelta 
      samples %d 
      modal interval %d \n''' % (sampleCounter,modal)

    fPtr.seek(0) # rewind
    return(datetime.timedelta(seconds=modal))


################ readTideFile  #############################
def readTideFileToLists(filename,timeFormat,
                        fieldSep='\t',
                        recSep='\n'):
    '''
    Reads date-time, tide, and other fields from the file or stdin into lists.
    Returns three lists: time(datetime objects), depth(float), and a list
    of other fields (contained with a list element, i.e., [[f1,f2,..],..]
    '''

    DTlist = []
    depthList = []
    otherFieldList = []

    sys.stderr.write("FILENAME: %s\n" % str(filename))

    infile = open(filename,"r")

    for line in infile:

        if ( re.search(commentRE,line) or ( re.search(blankRE,line))):
                 continue
        line.strip()
        (DT,depth,otherFields) = findTideFields(line,timeFormat)
        if(DT != None and depth != None):
            DTlist.append(DT)
            depthList.append(depth)
            otherFieldList.append(otherFields)
    return(DTlist,depthList,otherFieldList)

######################## findTideFields #####################
def findTideFields(line,timeFormat,
                   fieldSep='\t',
                   recSep='\n'):
    '''
    using the specified timeFormat (caris,matlab,UNIXepoch,..),
    this routine reads the data of a single line, and returns the
    fields
    '''

    DT = None # should become a datetime object
    depth = None # should become a float
    fields = otherFields = []

    if(fieldSep == '\t'):
        fields = line.split()
    else:
        fields = line.split(fieldSep)

    if timeFormat == 'caris':
        tStr = fields[0] + " " + fields[1]
        DT = datetime.datetime.strptime(tStr,timeFmts[timeFormat])
        depth = float(fields[2])
        otherFields = fields[3:]

    elif timeFormat ==  'matlab':
        Y = int(fields[0])
        m = int(fields[1])
        d = int(fields[2])
        H = int(fields[3])
        M = int(fields[4])
        S = float(fields[5])
        DT = datetime.datetime(year=Y
                               ,month=m
                               ,day=d
                               ,hour=H
                               ,minute=M
                               ,second=S)
        depth = float(fields[6])
        otherFields = fields[7:]

    elif timeFormat == 'UNIXepoch':
        DT=datetime.datetime.utcfromtimestamp(float(fields[0]))
        depth = float(fields[1])
        otherFields = fields[2:]

    return(DT,depth,otherFields)

####################### tideOutput ###################

def tideOutput(out,
               timeFormat,
               dTime,
               waterlevel,
               otherFields=None,
               fieldSep='\t',
               recSep='\n'):
    '''
    Formats and outputs the tide data with time
    '''

    # time string formatting
    if timeFormat == 'UNIXepoch':
        timeStr = str(time.mktime(dTime.timetuple()))
    else:
        timeFormatStr = timeFmts[timeFormat]
        # generate a time string using datetime's strftime
        timeStr = dTime.strftime(timeFormatStr)
        if fieldSep != '\t':
            # substitute appropriate field separator if not standard '\t'
            timeStr = timeStr.replace(' ',fieldSep)

    resultStr = '%s%s%f' % (timeStr,fieldSep,waterlevel)
    if ((otherFields != None) and (len(otherFields) > 0)):
        for v in otherFields:
            resultStr += fieldSep + str(v)
    out.write(resultStr + recSep)

###################### join ############################
def join(list,sep):
    '''
    returns a string composed of the stringified 
    elements of list separated by the sep string
    '''

    slist = map(lambda x: str(x), list)
    result = string.join(slist,sep)
    return result

###################### dt2fSecs #################
def dt2fSecs(dt):
    '''
    takes a datetime.timedelta objects and returns a float
    representing seconds. Requires datetime & numpy
    '''
    import datetime
    import numpy as np

    return(dt.seconds + (10**(-6)) * dt.microseconds)

################ timeStr2seconds ##################
def timeStr2seconds(timeStr):
    '''
    parses the timeStr (format HH:MM:SS) and
    converts it into seconds
    '''
    (hours,minutes,seconds) = string.split(timeStr,sep=':')
    return (60.*60.* float(hours) + 60. * float(minutes) + float(seconds))

#################### datetime2epoch ##################
def datetime2epoch(dt):
    '''
    converts a datetime object into epoch time
    '''
    return time.mktime(dt.timetuple())

#################### epoch2datetime ###################
def epoch2datetime(et):
    '''
    converts epoch time to a datetime object
    '''
    return datetime.datetime.utcfromtimestamp(et)

###################
