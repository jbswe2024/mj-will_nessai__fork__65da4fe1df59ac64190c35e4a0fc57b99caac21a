#!/usr/bin/env python

"""
Example of running FlowProposal with Bilby on a gravitational wave likelihood

Based on the Bilby example: https://git.ligo.org/lscsoft/bilby
"""
import bilby
import numpy as np

import torch
torch.set_num_threads(1)

# The output from the sampler will be saved to:
# '$outdir/$label_flowproposal/'
# alongside the usual bilby outputs
outdir = './outdir/'
label = 'gw_example'

bilby.core.utils.setup_logger(outdir=outdir, label=label, log_level='DEBUG')

duration = 4.
sampling_frequency = 2048.

np.random.seed(151226)

injection_parameters = dict(
    total_mass=66., mass_ratio=0.9, a_1=0.4, a_2=0.3, tilt_1=0.5, tilt_2=1.0,
    phi_12=1.7, phi_jl=0.3, luminosity_distance=2000, theta_jn=0.4, psi=2.659,
    phase=1.3, geocent_time=1126259642.413, ra=1.375, dec=-1.2108)

waveform_arguments = dict(waveform_approximant='IMRPhenomPv2',
                          reference_frequency=50.)

# Create the waveform_generator using a LAL BinaryBlackHole source function
# We specify a function which transforms a dictionary of parameters into the
# appropriate parameters for the source model.
waveform_generator = bilby.gw.waveform_generator.WaveformGenerator(
    sampling_frequency=sampling_frequency,
    duration=duration,
    frequency_domain_source_model=bilby.gw.source.lal_binary_black_hole,
    parameter_conversion=(bilby.gw.conversion
                          .convert_to_lal_binary_black_hole_parameters),
    waveform_arguments=waveform_arguments)

# Set up interferometers.
ifos = bilby.gw.detector.InterferometerList(['H1', 'L1', 'V1'])
ifos.set_strain_data_from_power_spectral_densities(
    sampling_frequency=sampling_frequency, duration=duration,
    start_time=injection_parameters['geocent_time'] - 3)
ifos.inject_signal(waveform_generator=waveform_generator,
                   parameters=injection_parameters)

# Set up prior
# FlowProposal is designed to sample mass ratio and chirp mass
priors = bilby.gw.prior.BBHPriorDict()
priors.pop('mass_1')
priors.pop('mass_2')
priors['chirp_mass'] = bilby.prior.Uniform(
    name='chirp_mass', latex_label='$m_c$', minimum=13, maximum=45,
    unit='$M_{\\odot}$')
priors['mass_ratio'] = bilby.prior.Uniform(
    name='mass_ratio', latex_label='q', minimum=0.125, maximum=1.0)

# Only sample masses and source angles
for key in ['a_1', 'a_2', 'tilt_1', 'tilt_2', 'phi_12', 'phi_jl',
            'ra', 'dec', 'geocent_time', 'luminosity_distance', 'phase',
            'psi']:
    priors[key] = injection_parameters[key]

# Initialise GravitationalWaveTransient
likelihood = bilby.gw.likelihood.GravitationalWaveTransient(
    interferometers=ifos, waveform_generator=waveform_generator,
    phase_marginalization=False)

flow_config = {
    "lr": 0.0001,
    "batch_size": 500,
    "val_size": 0.1,
    "max_epochs": 200,
    "patience": 20,
    "model_config": {
        "n_blocks": 4,
        "n_neurons": 32,
        "n_layers": 2,
        "ftype": "realnvp",
        "kwargs": {
            "batch_norm_between_layers": True,
            "linear_transform": "lu"
        }
    }
}

# Run sampler
# Note we've added a post-processing conversion function, this will generate
# many useful additional parameters, e.g., source-frame masses.
result = bilby.core.sampler.run_sampler(
    likelihood=likelihood, priors=priors, sampler='flowproposal',
    outdir=outdir, injection_parameters=injection_parameters, label=label,
    conversion_function=bilby.gw.conversion.generate_all_bbh_parameters,
    nlive=2000, training_frequency=2000, rescale_parameters=True,
    update_bounds=True, flow_config=flow_config, poolsize=20000,
    flow_class='GWFlowProposal', analytic_priors=True, resume=False,
    reparameterisations={'inversion': True})

result.plot_corner()