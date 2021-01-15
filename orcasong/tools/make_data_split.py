#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility script that makes .list files for the concatenate_h5.py tool.

Usage:
    make_data_split.py CONFIG
    make_data_split.py (-h | --help)

Arguments:
    CONFIG  A .toml file which contains the configuration options.

Options:
    -h --help  Show this screen.

"""

__author__ = 'Michael Moser, Daniel Guderian'

import os
import toml
import docopt
import natsort as ns
import h5py
import random
import numpy as np

   
def parse_input():
    """
    Parses the config of the .toml file, specified by the user.

    Returns
    -------
    cfg : dict
        Dict that contains all configuration options from the input .toml file.

    """

    args = docopt.docopt(__doc__)
    config_file = args['CONFIG']

    cfg = toml.load(config_file)
    cfg['toml_filename'] = config_file

    return cfg


def get_all_ip_group_keys(cfg):
    """
    Gets the keys of all input groups in the config dict.

    The input groups are defined as the dict elements, where the values have the type of a dict.

    Parameters
    ----------
    cfg : dict
        Dict that contains all configuration options and additional information.

    Returns
    -------
    ip_group_keys : list
        List of the input_group keys.

    """
    ip_group_keys = []
    for key in cfg:
        if type(cfg[key]) == dict:
            ip_group_keys.append(key)

    return ip_group_keys


def get_h5_filepaths(dirpath):
    """
    Returns the filepaths of all .h5 files that are located in a specific directory.

    Parameters
    ----------
    dirpath: str
        Path of the directory where the .h5 files are located.

    Returns
    -------
    filepaths : list
        List with the full filepaths of all .h5 files in the dirpath folder.

    """
    filepaths = []
    for f in os.listdir(dirpath):
        if f.endswith('.h5'):
            filepaths.append(dirpath + '/' + f)

    #randomize order
    random.Random(42).shuffle(filepaths)
    
    return filepaths


def get_number_of_evts(file,dataset_key="y"):
    """
    Returns the number of events of a file looking at the given dataset.
    
    Parameters
    ----------
    file : h5 file
        File to read the number of events from.
    dataset_key : str
        String which specifies, which dataset in a h5 file should be used for calculating the number of events.

    Returns
    -------
    n_evts : int
        The number of events in that file.
    
    """

    f = h5py.File(file, 'r')
    dset = f[dataset_key]
    n_evts = dset.shape[0]
    f.close()
    
    return n_evts
    
def get_number_of_evts_and_run_ids(list_of_files, dataset_key='y', run_id_col_name='run_id'):
    """
    Gets the number of events and the run_ids for all hdf5 files in the list_of_files.

    The number of events is calculated based on the dataset, which is specified with the dataset_key parameter.

    Parameters
    ----------
    list_of_files : list
        List which contains filepaths to h5 files.
    dataset_key : str
        String which specifies, which dataset in a h5 file should be used for calculating the number of events.
    run_id_col_name : str
        String, which specifies the column name of the 'run_id' column.

    Returns
    -------
    total_number_of_evts : int
        The cumulative (total) number of events.
    mean_number_of_evts_per_file : float
        The mean number of evts per file.
    run_ids : list
        List containing the run_ids of the files in the list_of_files.

    """

    total_number_of_evts = 0
    run_ids = []

    for i, fpath in enumerate(list_of_files):
        f = h5py.File(fpath, 'r')

        dset = f[dataset_key]
        n_evts = dset.shape[0]
        total_number_of_evts += n_evts

        run_id = f[dataset_key][0][run_id_col_name]
        run_ids.append(run_id)

        f.close()

    mean_number_of_evts_per_file = total_number_of_evts / len(list_of_files)

    return total_number_of_evts, mean_number_of_evts_per_file, run_ids


def split(a, n):
    """
    Splits a list into n equal sized (if possible! if not, approximately) chunks.

    Parameters
    ----------
    a : list
        A list that should be split.
    n : int
        Number of times the input list should be split.

    Returns
    -------
    a_split : list
        The input list a, which has been split into n chunks.

    """
    # from https://stackoverflow.com/questions/2130016/splitting-a-list-into-n-parts-of-approximately-equal-length
    k, m = divmod(len(a), n)
    a_split = list((a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)))
    return a_split


def print_input_statistics(cfg, ip_group_keys):
    """
    Prints some useful information for each input_group.

    Parameters
    ----------
    cfg : dict
        Dict that contains all configuration options and additional information.
    ip_group_keys : list
        List of the input_group keys.

    """

    print('----------------------------------------------------------------------')
    print('Printing input statistics for your ' + cfg['toml_filename'] + ' input:')
    print('----------------------------------------------------------------------')

    print('Your input .toml file has the following data input groups: ' + str(ip_group_keys))
    print('Total number of events: ' + str(cfg['n_evts_total']))

    for key in ip_group_keys:
        print('--------------------------------------------------------------------')
        print('Info for group ' + key + ':')
        print('Directory: ' + cfg[key]['dir'])
        print('Total number of files: ' + str(cfg[key]['n_files']))
        print('Total number of events: ' + str(cfg[key]['n_evts']))
        print('Mean number of events per file: ' + str(round(cfg[key]['n_evts_per_file_mean'], 3)))
        print('--------------------------------------------------------------------')


def add_fpaths_for_data_split_to_cfg(cfg, key):
    """
    Adds all the filepaths for the output files into a list, and puts them into the cfg['output_dsplit'][key] location
    for all dsplits (train, validate, rest).

    Parameters
    ----------
    cfg : dict
        Dict that contains all configuration options and additional information.
    key : str
        The key of an input_group.

    """

    fpath_lists = {'train': [], 'validate': [], 'rest': []}
    for i, fpath in enumerate(cfg[key]['fpaths']):

        run_id = cfg[key]['run_ids'][i]

        for dsplit in ['train', 'validate', 'rest']:
            if 'run_ids_' + dsplit in cfg[key]:
                if cfg[key]['run_ids_' + dsplit][0] <= run_id <= cfg[key]['run_ids_' + dsplit][1]:
                    fpath_lists[dsplit].append(fpath)

    for dsplit in ['train', 'validate', 'rest']:
        if len(fpath_lists[dsplit]) == 0:
            continue

        n_files_dsplit = cfg['n_files_' + dsplit]
        fpath_lists[dsplit] = split(fpath_lists[dsplit], n_files_dsplit)
        if 'output_' + dsplit not in cfg:
            cfg['output_' + dsplit] = dict()
        cfg['output_' + dsplit][key] = fpath_lists[dsplit]


def make_dsplit_list_files(cfg):
    """
    Writes .list files of the datasplits to the disk, with the information in the cfg['output_dsplit'] dict.

    Parameters
    ----------
    cfg : dict
        Dict that contains all configuration options and additional information.

    """
    # check if //conc_list_files folder exists, if not create it.
    if not os.path.exists(cfg['output_file_folder'] + '/conc_list_files'):
        os.makedirs(cfg['output_file_folder'] + '/conc_list_files')
    
    print()
    print()
    print("In an run-by-run MC the run_id's might not be continuous.")
    print("Here are the actual numbers in the split sets:") 
    print("----------------------------------------------")
   
   #loop over the different specified sets
    for dsplit in ['train', 'validate', 'rest']:

        if 'output_' + dsplit not in cfg:
            continue
        
        print(dsplit,"set:")
        
        first_key = list(cfg['output_' + dsplit].keys())[0]
        n_output_files = len(cfg['output_' + dsplit][first_key])

        #initialize counter of events for all input groups
        imput_groups_dict = cfg['output_' + dsplit]
        final_number_of_events = np.zeros(len(imput_groups_dict))
        
        #loop over the number of outputfiles for each set
        for i in range(n_output_files):
            fpath_output = cfg['output_file_folder'] + '/conc_list_files/' + cfg['output_file_name'] + '_' + dsplit + '_' + str(i) + '.txt'

            # save the txt list 
            if 'output_lists' not in cfg:
                cfg['output_lists'] = list()
            cfg['output_lists'].append(fpath_output)

            with open(fpath_output, 'w') as f_out:
                for j in range(len(imput_groups_dict)):
                    keys = list(imput_groups_dict.keys())
                    
                    for fpath in imput_groups_dict[keys[j]][i]:
                        #also count here the actual sizes
                        final_number_of_events[j] += get_number_of_evts(fpath)
                        f_out.write(fpath + '\n')
        
        #and then print them
        for i in range(len(imput_groups_dict)):
            print(keys[i],":",int(final_number_of_events[i]))
       
        print("----------------------------------------------")
        
        
def main():
    """
    Main function to make the data split.
    """

    cfg = parse_input()

    ip_group_keys = get_all_ip_group_keys(cfg)

    n_evts_total = 0
    for key in ip_group_keys:
        print('Collecting information from input group ' + key)
        cfg[key]['fpaths'] = get_h5_filepaths(cfg[key]['dir'])
        cfg[key]['n_files'] = len(cfg[key]['fpaths'])
        cfg[key]['n_evts'], cfg[key]['n_evts_per_file_mean'], cfg[key]['run_ids'] = get_number_of_evts_and_run_ids(cfg[key]['fpaths'], dataset_key='y')

        n_evts_total += cfg[key]['n_evts']

    cfg['n_evts_total'] = n_evts_total
    print_input_statistics(cfg, ip_group_keys)

    if cfg['print_only'] is True:
        from sys import exit
        exit()

    for key in ip_group_keys:
        add_fpaths_for_data_split_to_cfg(cfg, key)

    make_dsplit_list_files(cfg)



if __name__ == '__main__':
    print("well, i am oin here")
    main()
