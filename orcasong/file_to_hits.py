#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Code that reads the h5 simulation files and extracts the necessary information for making event images."""

import numpy as np
#from memory_profiler import profile
#import line_profiler # call with kernprof -l -v file.py args


def get_primary_track_index(event_blob):
    """
    Gets the index of the primary (neutrino) track.

    Uses bjorkeny in order to get the primary track, since bjorkeny!=0 for the initial interacting neutrino.

    Parameters
    ----------
    event_blob : kp.io.HDF5Pump.blob
        HDF5Pump event blob.

    Returns
    -------
    primary_index : int
        Index of the primary track (=neutrino) in the 'McTracks' branch.

    """
    bjorken_y_array = event_blob['McTracks'].bjorkeny
    primary_index = np.where(bjorken_y_array != 0.0)[0][0]
    return primary_index


def get_time_residual_nu_interaction_mean_triggered_hits(time_interaction, hits_time, triggered):
    """
    Gets the time_residual of the event with respect to mean time of the triggered hits.

    This is required for vertex_time reconstruction, as the absolute time scale needs to be relative to the triggered hits.

    Parameters
    ----------
    time_interaction : float
        Time of the neutrino interaction measured in JTE time.
    hits_time : ndarray(ndim=1)
        Time of the event_hits measured in JTE time.
    triggered : ndarray(ndim=1)
        Array with trigger flags that specifies if the hit is triggered or not.

    """
    hits_time_triggered = hits_time[triggered == 1]
    t_mean_triggered = np.mean(hits_time_triggered, dtype=np.float64)
    time_residual_vertex = t_mean_triggered - time_interaction

    return time_residual_vertex


def get_hits(event_blob, geo, do_mc_hits, data_cuts, do4d):
    """
    Returns a hits array that contains [pos_x, pos_y, pos_z, time, triggered, channel_id (optional)].

    Parameters
    ----------
    event_blob : kp.io.HDF5Pump.blob
        Event blob of the HDF5Pump which contains all information for one event.
    geo : kp.Geometry
        km3pipe Geometry instance that contains the geometry information of the detector.
        Only used if the event_blob is from a non-calibrated file!
    do_mc_hits : bool
        Tells the function of the hits (mc_hits + BG) or the mc_hits only should be parsed.
        In the case of mc_hits, the dom_id needs to be calculated thanks to the jpp output.
    data_cuts : dict
        Specifies if cuts should be applied.
        Contains the keys 'triggered' and 'energy_lower/upper_limit' and 'throw_away_prob'.
    do4d : tuple(bool, str)
        Tuple that declares if 4D histograms should be created [0] and if yes, what should be used as the 4th dim after xyz.
        In the case of 'channel_id', this information needs to be included in the event_hits as well.

    Returns
    -------
    event_hits : ndarray(ndim=2)
        2D array that contains the hits data for the input event [pos_x, pos_y, pos_z, time, triggered, (channel_id)].

    """
    # parse hits [x,y,z,time]
    hits = event_blob['Hits'] if do_mc_hits is False else event_blob['McHits']

    if 'pos_x' not in event_blob['Hits'].dtype.names: # check if blob already calibrated
        hits = geo.apply(hits)

    if data_cuts['triggered'] is True:
        hits = hits.__array__[hits.triggered.astype(bool)]
        #hits = hits.triggered_hits # alternative, though it only works for the triggered condition!

    pos_x, pos_y, pos_z = hits.pos_x, hits.pos_y, hits.pos_z
    hits_time = hits.time
    triggered = hits.triggered

    ax = np.newaxis
    event_hits = np.concatenate([pos_x[:, ax], pos_y[:, ax], pos_z[:, ax], hits_time[:, ax], triggered[:, ax]], axis=1) # dtype: np.float64

    if do4d[0] is True and do4d[1] == 'channel_id' or do4d[1] == 'xzt-c':
        event_hits = np.concatenate([event_hits, hits.channel_id[:, ax]], axis=1)

    return event_hits


def get_tracks(event_blob, file_particle_type, event_hits, prod_ident):
    """
    Returns the event_track, which contains important event_info and mc_tracks data for the input event.

    Parameters
    ----------
    event_blob : kp.io.HDF5Pump.blob
        Event blob of the HDF5Pump which contains all information for one event.
    file_particle_type : str
        String that specifies the type of particles that are contained in the file: ['undefined', 'muon', 'neutrino'].
    event_hits : ndarray(ndim=2)
        2D array that contains the hits data for the input event.
    prod_ident : int
        Optional int that identifies the used production, more documentation in the docs of the main function.

    Returns
    -------
    event_track : ndarray(ndim=1)
        1D array that contains important event_info and mc_tracks data for the input event.

        If file_particle_type = 'undefined':
        [event_id, run_id, (prod_ident)].

        If file_particle_type = 'neutrino'/'muon':
        [event_id, particle_type, energy, is_cc, bjorkeny, dir_x, dir_y, dir_z, time_track, run_id,
        vertex_pos_x, vertex_pos_y, vertex_pos_z, time_residual_vertex/n_muons, (prod_ident)].

    """
    # parse EventInfo and Header information
    event_id = event_blob['EventInfo'].event_id[0]
    if 'Header' in event_blob: # if Header exists in file, take run_id from it. Else take it from RawHeader.
        run_id = event_blob['Header'].start_run.run_id.astype('float32')
    else:
        run_id = event_blob['RawHeader'][0][0].astype('float32')

    # collect all event_track information, dependent on file_particle_type

    if file_particle_type == 'undefined':
        particle_type = 0
        track = [event_id, run_id, particle_type]

    elif file_particle_type == 'muon':
        # take index 1, index 0 is the empty neutrino mc_track
        particle_type = event_blob['McTracks'][1].type # assumed that this is the same for all muons in a bundle
        is_cc = event_blob['McTracks'][1].is_cc # always 1 actually
        bjorkeny = event_blob['McTracks'][1].bjorkeny # always 0 actually
        time_interaction = event_blob['McTracks'][1].time  # same for all muons in a bundle
        n_muons = event_blob['McTracks'].shape[0] - 1 # takes position of time_residual_vertex in 'neutrino' case

        # sum up the energy of all muons
        energy = np.sum(event_blob['McTracks'].energy)

        # all muons in a bundle are parallel, so just take dir of first muon
        dir_x, dir_y, dir_z = event_blob['McTracks'][1].dir_x, event_blob['McTracks'][1].dir_y, event_blob['McTracks'][1].dir_z

        # vertex is the weighted (energy) mean of the individual vertices
        vertex_pos_x = np.average(event_blob['McTracks'][1:].pos_x, weights=event_blob[4]['McTracks'][1:].energy)
        vertex_pos_y = np.average(event_blob['McTracks'][1:].pos_y, weights=event_blob[4]['McTracks'][1:].energy)
        vertex_pos_z = np.average(event_blob['McTracks'][1:].pos_z, weights=event_blob[4]['McTracks'][1:].energy)

        track = [event_id, particle_type, energy, is_cc, bjorkeny, dir_x, dir_y, dir_z, time_interaction, run_id,
                 vertex_pos_x, vertex_pos_y, vertex_pos_z, n_muons]

    elif file_particle_type == 'neutrino':
        p = get_primary_track_index(event_blob)
        particle_type = event_blob['McTracks'][p].type
        energy = event_blob['McTracks'][p].energy
        is_cc = event_blob['McTracks'][p].is_cc
        bjorkeny = event_blob['McTracks'][p].bjorkeny
        dir_x, dir_y, dir_z = event_blob['McTracks'][p].dir_x, event_blob['McTracks'][p].dir_y, event_blob['McTracks'][p].dir_z
        time_interaction = event_blob['McTracks'][p].time  # actually always 0 for primary neutrino, measured in MC time
        vertex_pos_x, vertex_pos_y, vertex_pos_z = event_blob['McTracks'][p].pos_x, event_blob['McTracks'][p].pos_y, \
                                                   event_blob['McTracks'][p].pos_z

        hits_time, triggered = event_hits[:, 3], event_hits[:, 4]
        time_residual_vertex = get_time_residual_nu_interaction_mean_triggered_hits(time_interaction, hits_time, triggered)

        track = [event_id, particle_type, energy, is_cc, bjorkeny, dir_x, dir_y, dir_z, time_interaction, run_id,
                 vertex_pos_x, vertex_pos_y, vertex_pos_z, time_residual_vertex]

    else:
        raise ValueError('The file_particle_type "', str(file_particle_type), '" is not known.')

    if prod_ident is not None: track.append(prod_ident)

    event_track = np.array(track, dtype=np.float64)

    return event_track


def get_event_data(event_blob, file_particle_type, geo, do_mc_hits, data_cuts, do4d, prod_ident):
    """
    Reads a km3pipe blob which contains the information for one event and returns a hit array and a track array
    that contains all relevant information of the event.

    Parameters
    ----------
    event_blob : kp.io.HDF5Pump.blob
        Event blob of the HDF5Pump which contains all information for one event.
    file_particle_type : str
        String that specifies the type of particles that are contained in the file: ['undefined', 'muon', 'neutrino'].
    geo : kp.Geometry
        km3pipe Geometry instance that contains the geometry information of the detector.
        Only used if the event_blob is from a non-calibrated file!
    do_mc_hits : bool
        Tells the function of the hits (mc_hits + BG) or the mc_hits only should be parsed.
        In the case of mc_hits, the dom_id needs to be calculated thanks to the jpp output.
    data_cuts : dict
        Specifies if cuts should be applied.
        Contains the keys 'triggered' and 'energy_lower/upper_limit' and 'throw_away_prob'.
    do4d : tuple(bool, str)
        Tuple that declares if 4D histograms should be created [0] and if yes, what should be used as the 4th dim after xyz.
        In the case of 'channel_id', this information needs to be included in the event_hits as well.
    prod_ident : int
        Optional int that identifies the used production, more documentation in the docs of the main function.
    geo : None/kp.Geometry
        If none, the event_blob should already contain the calibrated hit information (e.g. pos_xyz).
        Else, a km3pipe Geometry instance that contains the geometry information of the detector.

    Returns
    -------
    event_hits : ndarray(ndim=2)
        2D array containing the hit information of the event [pos_xyz, time, triggered, (channel_id)].

    event_track : ndarray(ndim=1)
        1D array containing important MC information of the event,
        [event_id, particle_type, energy, is_cc, bjorkeny, dir_x, dir_y, dir_z, time_track, run_id,
        vertex_pos_x, vertex_pos_y, vertex_pos_z, time_residual_vertex, (prod_ident)].

    """
    event_hits = get_hits(event_blob, geo, do_mc_hits, data_cuts, do4d)
    event_track = get_tracks(event_blob, file_particle_type, event_hits, prod_ident)

    return event_hits, event_track