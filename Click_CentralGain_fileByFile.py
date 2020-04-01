from anlffr.helper import biosemi2mne as bs
import mne
import numpy as np
import os
import fnmatch
from scipy.signal import savgol_filter as sg
from scipy.io import savemat
from anlffr.spectral import mtplv, mtphase
import pylab as pl


# Setup bayesian-weighted averaging
def bayesave(x, trialdim=0, timedim=1, method='mean', smoothtrials=19):
    ntrials = x.shape[trialdim]
    if method == 'mean':
        summary = x.mean(axis=trialdim) * (ntrials) ** 0.5
    else:
        summary = np.median(x, axis=trialdim) * (ntrials) ** 0.5

    ntime = x.shape[timedim]
    wts = 1 / np.var(x - summary, axis=timedim, keepdims=True)
    wts = sg(wts, smoothtrials, 3, axis=trialdim)  # Smooth the variance
    normFactor = wts.sum()
    wts = wts.repeat(ntime, axis=timedim)
    ave = (x * wts).sum(axis=trialdim) / normFactor
    return ave


# Adding Files and locations
froot = 'D:/DATA/ABR/'

# Done: ['S072', 'S032', 'S077', 'S177', 'S179', 'S172', 'S165', 'S152',
#        'S060', 'S147', 'S091', 'S076', 'S051', 'S125', 'S083', 'S153',
#            'S150', 'S158', 'S160', 'S159', 'S061', 'S111', 'S160', 'S155',
#            'S061', 'S046', 'S166', 'S108', 'S159', 'S107', 'S115', 'S073',
#            'S074', 'S091', 'SM', 'S049', 'S025', 'S011', 'S037', 'S039',
#            'S043', 'S052', 'S046', 'S050', 'S053''S012', 'S018', 'S017',
#             'S019', 'S001', 'S020', 'S024', 'S026', 'S028', 'S027''S148',
#            'S034', 'S042', 'S057', 'S064',
#             'S134', 'S130', 'S114', 'S086', 'S084', 'S078''S075',
#           'S069', 'S157', 'S031', 'S163',  'S215', 'S068', 'S088', 'S217',
#            'S213']
subjlist = ['S209', 'S210']

# Crashed: ['S059', 'S040',]

earlist = ['L', 'R']

for subj in subjlist:
    for ear in earlist:
        if ear == 'L':
            conds = [[3, 9], [5, 10], [6, 12]]
            names = ['_L_soft', '_L_moderate', '_L_loud']
        else:
            conds = [[48, 144], [80, 160], [96, 192]]
            names = ['_R_soft', '_R_moderate', '_R_loud']

        print 'Running Subject', subj, ear, 'ear'
        for ind, cond in enumerate(conds):
            name = names[ind]
            print 'Doing condition ', cond
            fpath = froot + '/' + subj + '/'
            # Use for tinnitus subjects
            # bdfs = fnmatch.filter(os.listdir(fpath), subj + '_tinnitus_ABR*.bdf')

            # Use for regular subjects
            bdfs = fnmatch.filter(os.listdir(fpath), subj + '_ABR*.bdf')

            if len(bdfs) >= 1:
                for k, bdf in enumerate(bdfs):
                    edfname = fpath + bdf
                    # Load data and read event channel
                    extrachans = [u'GSR1', u'GSR2', u'Erg1', u'Erg2', u'Resp',
                                  u'Plet', u'Temp']
                    raw, eves = bs.importbdf(edfname, nchans=36,
                                             extrachans=extrachans)
                    raw.set_channel_types({'EXG3': 'eeg', 'EXG4': 'eeg'})

                    # Pick channels to not include in epoch rejection
                    raw.info['bads'] += ['EXG3', 'EXG4', 'A1', 'A3',
                                         'A4', 'A5', 'A8', 'A9',
                                         'A10', 'A11', 'A12', 'A13', 'A14',
                                         'A15', 'A16', 'A17', 'A18', 'A19',
                                         'A20', 'A21', 'A22', 'A23', 'A24',
                                         'A25', 'A26', 'A27', 'A30']
                    # Filter the data
                    raw.filter(l_freq=2., h_freq=3000, picks=np.arange(36))

                    # Epoch the data
                    tmin, tmax = 0.0016, 0.1
                    bmin, bmax = 0.0016, 0.1
                    rejthresh = 100e-6

                    # Check if condition has events in the file:
                    if ((np.equal(eves[:, 2], cond[0]).sum() == 0) or
                        (np.equal(eves[:, 2], cond[0]).sum() == 0)):
                        continue

                    epochs = mne.Epochs(raw, eves, cond, tmin=tmin, proj=False,
                                        tmax=tmax, baseline=(bmin, bmax),
                                        picks=np.arange(36),
                                        reject=dict(eeg=rejthresh),
                                        verbose='WARNING')
                    xtemp = epochs.get_data()
                    t = epochs.times * 1e3 - 1.6  # Adjust for delay and use ms
                    # Reshaping so that channels is first
                    if(xtemp.shape[0] > 0):
                        xtemp = xtemp.transpose((1, 0, 2))
                        if ('x' not in locals()) or (k == 0):
                            x = xtemp
                        else:
                            x = np.concatenate((x, xtemp), axis=1)
                    else:
                        continue
            else:
                RuntimeError('No BDF files found!!')

            # Average data
            goods = [1, 5, 6, 27, 28, 30, 31]
            if ear == 'L':
                refchan = 34
            else:
                refchan = 35

            y = x[goods, :, :].mean(axis=0) - x[refchan, :, :]

            params = dict(Fs=raw.info['sfreq'], tapers=[4, 7],
                          fpass=[1, 4000], itc=0)
            plv, f = mtplv(y, params)
            ph, f_ph = mtphase(y, params)

            tdresp = np.median(y, axis=0) * 1.0e6  # Just time domain average

            # Make dictionary and save
            mdict = dict(t=t, x=tdresp, f=f, f_ph=f_ph, ph=ph, plv=plv)
            savepath = froot + '/CentralGainResults/'
            savename = subj + name + '_CentralGain.mat'
            savemat(savepath + savename, mdict)

            pl.plot(f, plv)
