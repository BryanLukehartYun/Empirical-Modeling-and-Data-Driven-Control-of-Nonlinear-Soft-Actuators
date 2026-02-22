## Pneumatic Artificial Muscle Nonlinear Dynamics Analysis and SYSID
Nonlinear GNC framework for Pneumatic Artificial Muscles (PAMs). Features NLARX system identification (Sigmoid, Wavelet, idTreePartition) and robust state estimation (Kalman Filters) designed to reject complex hysteresis-induced bias and non-differentiable gradient spikes. Also contains Monte Carlo regarding Unscented Kalman Filter and Model Predictive Control. 



## **Licensing & Intellectual Property**

This project utilizes a **dual-licensing framework** to distinguish between functional software and technical research analysis:

* Software & Scripts: All MATLAB source code (.m) and supporting functions are provided under the **MIT License**.

* Technical Analysis: The reports, unique figure interpretations, and design-decision narratives contained in the README files are copyright © 2026 Bryan Lukehart-Yun and licensed under **CC BY-NC-ND 4.0**. 

* Data Attribution: The provided 10,000-sample dataset containing multiple permutations (.mat) is a series of randomized, non-representative slices **intended for architectural demonstration**.
Full high-fidelity datasets (15M+ samples) and theoretical derivations are reserved for upcoming publications in T-RO, IJRR, and Data In Brief. 

* **Future Release** The complete 15-million-sample global dataset will be published via Data in Brief; this repository will be updated with the public access links upon release. 

**Citation**: If you utilize this GNC framework or the UKF bias-rejection analysis in your work, please attribute it to this repository or the forthcoming Zenodo DOI. 