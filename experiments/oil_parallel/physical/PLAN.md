# Finite-layer physical experiment (frozen before fitting)

One candidate; no fitted diagnostic ablation. Compare existing v1/v3.
Assume an ideal diffuse white backing Rg=1, identical physical application
thickness across all swatches, no surface reflection and additive effective
mass-based K and S. None is a measured property of the archive.

Let q=K/S, a=1+q, b=sqrt(q(q+2)), tau=S*x,
h=b*coth(b*tau), and R=(1-Rg*(a-h))/(a+h-Rg).
At q=0 use h=1/tau. S_W(lambda)=1 fixes the optical scale; x is a
wavelength-independent optical-thickness multiplier, not a thickness in mm.
At each proposal invert R(q,S_j*x)=measured pure R_j by monotone bisection.
Then K_j=q_j*S_j and mixture K=sum(c_j*K_j), S=sum(c_j*S_j).
Pure endpoints are exact constraints; 93 log-S parameters plus log-x =94.

Bounds log-S=[-9.210340371976184,9.210340371976184]; x=[0.1,100].
Fixed starts (all three chromatic log-S, x): (0,0.3), (log(0.1),3),
(log(10),30). Select lowest training objective, including nonconverged
results only if no run converges (then label failed and do not promote).
Residual is spectral error/sqrt(number of fitting band values), plus
sqrt(1e-4/(3*29))*second differences of log-S and
sqrt(1e-8/93)*log-S. No thickness prior. scipy TRF with numerical sparse
Jacobian, max_nfev=200, ftol=xtol=gtol=1e-8; no evaluation-driven retuning.
Inverse q uses 55 bisection iterations after doubling the initial upper
bound max(1,2*q_infinite) until R(upper,tau)<=pure R (maximum 60 doublings,
then explicit failure). Finite q>=q_infinite on a white backing. The
initial incorrect inequality was caught in review before any real fit.

Run all three starts on 29 fit/16 multicolor and three whole-pair-family
exclusion fits, using the fixed shared design. Freeze fits before assessment.
Report all errors with existing unclipped 31-band truncated D65 helpers;
all assessment is exploratory because rows were previously exposed.
Validate independently using matrix exponential of two-flux ODE,
thin/thick limits, inversion and synthetic endpoint/recipe cases.

Equation reference: Paul Kubelka, New Contributions to the Optics of Intensely
Light-Scattering Materials. Part I (1948),
https://opg.optica.org/josa/abstract.cfm?uri=josa-38-5-448 .
This experiment tests an assumed finite layer, not paper-specific fidelity or
a determination of backing/thickness from measurements.
