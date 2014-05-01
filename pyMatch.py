#!/usr/bin/env python2

"""

pyMatch Component --> Template Matching in Python

This python script uses MRtools to read in a nifti image template (Data class), and match
a list of user specified images to the template (Match class).  Usage could be to match
components (individual functional networks) from an individual ica analysis to the 
most similar component from a group ica (group networks) analysis, OR to match a group 
significant result from one modality to group networks.  The images used for matching
will first be filtered (getting rid of high frequency components) and then matched.
Inputs should be as follows:

INPUT:
-h, --help      Print this usage
-s --subs=      Single column text file w/ list of subject (or group) folders containing components
-t --template=  The template image to match, such as a group network
-i --images =   Single column text file with a list of component images in folders
-o --output=    Name of output folder.  If not specified, will use pwd

If you input a list of subjects longer than one, keep in mind that each should have the
corresponding component images in the designated folder.  Whether 3D or 4D, the first
timepoint will be used by default to extract data.  If an image's first timepoint is
empty, the script will try the second.  If the second is also empty, it will exit with
error, because there is something wrong with your template or image!

USAGE: python pyMatch.py --subs=sublist.txt --template=/path/to/image.nii.gz --images=imagelist.txt --output=/path/for/outfile

Intended usage is for one template for 1+ subjects/groups with a list of component images.  
Currently only supports matching 3D images (if 4D input, first timepoint will be used)

OUTPUT: (template_name)_bestcomps.txt and (template_name)_beststats.txt w/ top 3 components for each subject/group

"""

__author__ = "Vanessa Sochat (vsochat@stanford.edu)"
__version__ = "$Revision: 1.0 $"
__date__ = "$Date: 2011/08/20 $"
__license__ = "Python"

import os
import sys
import MRtools # includes classes Data, Filter, and Match 
import operator
import getopt
import re
import numpy as np

# RESULT------------------------------------------------------------------------------
class pyMatchRes:
    def __init__(self,output,filename):
        self.output = output      # output folder
        self.file = filename      # filename
        self.name = None
        self.fullpath = None      # Full path to output stats file
	self.setPath()

    def getFullPath(self):
        return self.fullpath

    def getImPath(self):
        return self.imagepath

    def setPath(self):
        base,ext = os.path.splitext(os.path.basename(self.file))
	self.fullpath = self.output + "/" + base + "_beststats.txt"
        self.name = base

    # writeHeader and addResult print a beststats.txt file for import into excel, etc.
    def writeHeader(self,header):
        try:
	    fopen = open(self.fullpath,'w')
	    fopen.write(header + "\n")
            fopen.close()
	except:
            print "Cannot write file " + self.fullpath + ". Exiting"
            sys.exit()
        
    def addResult(self,result):
	try:
	    fopen = open(self.fullpath,'a')
	    fopen.write(result)
            #for entry in result:
	    #    fopen.write(str(entry) + " ",)
	    fopen.write("\n")
            fopen.close()
	except:
            print "Cannot write file " + self.fullpath + ". Exiting"
            sys.exit()

    # Prints a single column text file, template image at top, in format /full/image/path:match_score
    def addImages(self,imagelist):
        iopen = open(self.imagepath,'a')
        for imgname in imagelist:
            iopen.write(str(imgname) + "\n")
        iopen.close()
	

# USAGE ---------------------------------------------------------------------------------
def usage():
    print __doc__

# Reads single column text file, returns list
def readInput(readfile):
    flist = []
    print "Reading input file " + readfile
    try:
        rfile = open(readfile,'r')
	for line in rfile:
	    flist.append(line.rstrip("\n").rstrip())
        rfile.close()
    except:
        print "Cannot open file " + readfile + ". Exiting"
        sys.exit()
    flist
    return flist

# Check that all component files exist for each subject
# Return dict of images that are found
def checkInput(subinput,compinput):
   print "Checking for all components images for each output/subject..."
   found = dict()
   count = 0
   for sub in subinput:
     tmp = list() 
     if sub:
       for comp in compinput:
         if os.path.isfile(sub + "/" + comp):
           tmp.append(sub + "/" + comp)
           count = count + 1
       print "Found " + str(len(tmp)) + " components for subject " + sub + "!"
       found[sub] = tmp
   if count == 0:
     print "No subject images found - analysis will not be continued."
     sys.exit(32) 
   return found 

# MAIN ----------------------------------------------------------------------------------
def main(argv):
    try:
        opts, args = getopt.getopt(argv, "ht:s:i:o:", ["help","template=","subs=","images=","output="])

    except getopt.GetoptError:
        usage()
        sys.exit(2)
    
    # First cycle through the arguments to collect user variables
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()    
        if opt in ("-t","--template"):
            input1 = arg
        if opt in ("-i", "--images"):
            input2 = arg
	if opt in ("-s","--subs"):
            sublist = arg
        if opt in ("-o","--output"):
            output = arg

    # Get list of subject and component paths
    subfile = readInput(sublist)
    imgfiles = readInput(input2)

    # Check that all components exist for each subject
    # Return a dict of found images for each sub (index)
    found = checkInput(subfile,imgfiles)
        
    # Read in template image to MRtools Data object, and get xyz and raw data
    Template = MRtools.Data(input1,'3D')
    
    # Prepare output file
    if not output:
        output = os.getcwd()
    Result = pyMatchRes(output,Template.name)        
    Result.writeHeader([input1 + ":template"])

    # TEMPLATE WORK ------------------------------------------------------------------------
    # Identify voxels that meet criteria.  
    Match = MRtools.Match(Template)        # Create an MRTools Match object to do the job!
    Match.setIndexCrit('>',0)              # Set criteria for filtering the template image
    Match.genIndexMNI()                    # Generate the indices based on specified filter in MNI space
                                           # Match.indexes[n][0] is x coordinate in mm 
                                           # Match.indexes[n][1] is y coordinate in mm
                                           # Match.indexes[n][2] is z coordinate in mm

    # COMPONENT IMAGE WORK --------------------------------------------------------------------------   
    # For each subject, compute the similarity score of all components belonging to subject
    # with the template
                    
    # Note that "subject" might also be a group .gica folder, or a dual regression results folder, however the idea is the same  
    # This script assumes that input image lists have already been filtered, etc.

    # We are going to put results into a matrix - terms will be in columns, images in rows, values are overlap match scores
    # So this script will output a single column for the term
    matrix = list()
    rowLabels = []

    print "Computing similarity scores..."    
    for subject,images in found.iteritems():
      print "Processing images for subject " + subject + "..."
      
      # Add image names to our rowlabels
      rowLabels.append(images)
      
      for img_current in images:
        if img_current:
          print img_current
          # If submit by the ica+ script, the "subject" is a specified DR result folder
          # and the images to match are those whose IC components have passed filtering
          # the DR images and IC networks that pass filter results are in the original
          # gica directory under "filter"
          try:
              # Use MRtools Data class to read in image
              Contender = MRtools.Data(img_current,'3D')
              # Since these have already been selected from filtered IC networks, we add each one
              Match.addComp(Contender)
          except:
              print "Problem with " + img_current + ". Exiting!"
              sys.exit()    
                    
      if len(Match.components) > 0:

        # DO TEMPLATE MATCHING - commented out code is for old method to get top three scores / subject
        # Get dictionaries of activation overlap scores, and activation overlap absolute value scores
        # There is one for each subject, indexed by the component image name
        # activation_overlap,activation_overlapabs = Match.matchOverlap()

        # CHOOSE TOP RESULTS ----------------------------------------------------------------------------------	
        # When we finish cycling through the components, we want to find the top three matching (the most similar) components
        # We rank with activation_overlapabs, which is looking at absolute activation values (negative and positive Z ranked equally)
			
        # topmatch = list(sorted(activation_overlapabs.iteritems(), key=operator.itemgetter(1))[-1])
        # secondmatch = list(sorted(activation_overlapabs.iteritems(), key=operator.itemgetter(1))[-2])
        # thirdmatch = list(sorted(activation_overlapabs.iteritems(), key=operator.itemgetter(1))[-3])

        # Print information about the top three to the final results log
        # resultitem = [subject,os.path.basename(topmatch[0]),topmatch[1],os.path.basename(secondmatch[0]),secondmatch[1],os.path.basename(thirdmatch[0]),thirdmatch[1]]
        # Result.addResult(resultitem)

        # Add full paths to images to bestcomps.txt file, to create AIM templates for
        # Result.addImages([str(topmatch[0]) + ":" + str(topmatch[1]),str(secondmatch[0]) + ":" + str(secondmatch[1]),str(thirdmatch[0]) + ":" + str(thirdmatch[1])])

        # print "Top matches for " + Template.name + " are:"
        # print "    1) " + str(os.path.basename(topmatch[0]))
        # print "    2) " + str(os.path.basename(secondmatch[0]))
        # print "    3) " + str(os.path.basename(thirdmatch[0])) + "\n"

        # print "Full results printed to: " + Result.getFullPath()
        # print "Image list printed to: " + Result.getImPath()

        # Clear the Match object to prepare for the next subject or group, if applicable


        # DO TEMPLATE MATCHING - This code is for generating list of dictionaries, 
        resultitem = Match.matchOverlapMatrix() # outputs a dictionary of match scores, each to template

        # For each match score, add to output file
        for i,score in resultitem.iteritems():
          print "Adding " + i + " " + str(score)
          Result.addResult(i + "\t" + str(score))
        Match.reset()
      
      else:
        print "No matches for " + subject + "!"

if __name__ == "__main__":
    main(sys.argv[1:])
