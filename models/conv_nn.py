import torch
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.append(library_path)
from models.cnn_classifier import Classifier
from models.cnn_segmentator import Segmentator
from processing_utils.roi import ROI
import json
import time
from main import peakonly
from os import listdir
from os.path import isfile, join, isdir
from processing_utils.run_utils import preprocess, correct_classification, get_borders, Feature
from main import sub_rois
from roi import ROI as poROI
from os import listdir
import statistics
from os.path import isfile, join, isdir
import numpy as np
import csv
import pandas as pd
import time
import csv
start = time.time()
# %load_ext autoreload
# %autoreload 2
# checking if gpu is available
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')


def import_cnn(classifier):
    # importing the pre-trained CNN classifier and loading weights
# the convolutional neural network is defined
    classifier = Classifier().to(device)
    path2classifier_weights = os.path.join(library_path,'data', 'weights', 'Classifier.pt')
    classifier.load_state_dict(torch.load(path2classifier_weights, map_location=device))
    classifier.eval()

    return classifier

def import_segmentator():
    # the second pre trained CNN for peak integration is imported and the weights loaded 
    segmentator = Segmentator().to(device)
    path2segmentator_weights = os.path.join(library_path, 'data', 'weights', 'Segmentator.pt')
    segmentator.load_state_dict(torch.load(path2segmentator_weights, map_location=device))
    segmentator.eval()

    return segmentator

def access_data(mzml_filepath):
    # firstly we access the directory to look for the file path
    directories = [f for f in listdir(mzml_filepath) if isdir(join(mzml_filepath, f))]
    for dir in directories:
        dir = mzml_filepath + "/" + dir
        onlyfiles = [f for f in listdir(dir) if isfile(join(dir, f))]
        rois = []
        # open files in the directory which are json files
        for files in onlyfiles:
            with open(dir + "/" + files) as json_file:
                # we use a try and catch as there are hidden files
                try:
                    data = json.load(json_file)
                except: 
                    continue
                num_peaks = data["number of peaks"]
                # get only the files where the number of peaks is = 1
            if num_peaks == 1:
                rois += peakonly(onlyfiles)
    # get the time for the CNN to process Rois, continued in the function below
    end = time.time()

def use_rois():
        # get the rois as sub rois from the main
    start = time.time()
    split_rois=[]
    for idx, roi in enumerate(rois):
        # get the rois which have at least 5 scans
        if roi.peak_list[-1].scan - roi.peak_list[0].scan >= 5:
            # create a file and write the first results
            with open("Results/CNN_roi_" + str (idx) + ".csv", 'w') as file:
                percentage = 10
                split_rois = sub_rois(roi,percentage)
                file.write("percentage,result,mz,rt,scan,max_intensity" + "\n")
                # this method converts the sub_rois into the peakonly roi objects
                for i in range(len(split_rois)-1):
                    rr = poROI([split_rois[i].peak_list[0].scan,split_rois[i].peak_list[-1].scan],
                            [split_rois[i].peak_list[0].rt,split_rois[i].peak_list[-1].rt],
                            [p.i for p in split_rois[i].peak_list],
                            [split_rois[i].peak_list[0].mz,split_rois[i].peak_list[-1].mz],split_rois[i].mean_mz)
                            # pass the signal which is a list of intensitites to the cnn and interpolate it
                    signal = preprocess(rr.i, torch.device('cpu'), interpolate=True,length=256)
                    classifier_output, _ = classifier(signal)
                    _, segmentator_output = segmentator(signal)
                    classifier_output = classifier_output.data.cpu().numpy()
                    # label is the initial output of the cnn
                    label = np.argmax(classifier_output)
                    result = label
                    # write the output as 0 for non peaks and 1 for classified peaks
                    if result > 0.5:
                        result = 1
                    else: 
                        result = 0
                    file.write(str(i*percentage + percentage) + "," + str(result)+ "," + str(np.array(rr.mz))+ "," + str(np.array(rr.rt)) + "," + str(np.array(rr.scan)) + "," + str(np.max(rr.i)) + "\n")



def append_results():
        # open results to start the final statistics 
    onlyfiles = [f for f in listdir("Results") if isfile(join("Results", f))]
    rois = []
    percentages = []
    intensities = []
    mz = []
    rt = []
    cnn_percentage = []
    num_rois = 0
    num_classified_rois = 0
    # loop over the files and append the final percentage and result
    for files in onlyfiles:
        findpercentage = False
        file_name = files
        with open("Results/"+files, 'r') as file:
            next(file)
            for line in file:
                line = line.split(",")
                if line[1].strip()== str (1):
                    percentage = line[0].strip()
                    result = line[1].strip()
                    # only append the percentage correlated to the result that has been classified as 1
                    if (int(result)) == 1 and not findpercentage:
                        cnn_percentage.append(int(percentage))
                        findpercentage = True
                        print(cnn_percentage)
                        # because of double arrays use split and the one value out of the mz, rt
                    intensity = line[5].strip()
                    percentages.append(line[0])
                    mzstart = line[2].split()[0]
                    mzend = line[2].split()[1]
                    mzstart = mzstart.replace("[","")
                    mzend= mzend.replace("]","")
                    mzvalue = statistics.mean([float(mzstart), float(mzend)])
                    mz.append(mzvalue)
                    rt_start = line[3].split()[0]
                    rt_end = line[3].split()[1]
                    rt_start = rt_start.replace("[","")
                    rt_end= rt_end.replace("]","")
                    rtvalue = statistics.mean([float(rt_start), float(rt_end)])
                    rt.append(rtvalue)
                    num_classified_rois += 1
                    intensity = float(intensity.replace("\n",""))
                    intensities.append(intensity)
                num_rois += 1
                # calculate the mean of these values
    mean_mz = statistics.mean(mz)
    mean_rt = statistics.mean(rt)
    intensity = statistics.mean(intensities)
    percent = statistics.mean(cnn_percentage)

    with open('Final_mean_results.csv', 'w', newline='') as csvfile: 
        meanwriter = csv.writer(csvfile, delimiter=' ',quotechar='|',quoting=csv.QUOTE_MINIMAL)
        meanwriter.writerow(["cnn_value_count","classified_rois","mean_mz","mean_rt","mean_max_intensity"])

# library_path = '/Users/salvatoreesposito/Desktop/peakonly'
