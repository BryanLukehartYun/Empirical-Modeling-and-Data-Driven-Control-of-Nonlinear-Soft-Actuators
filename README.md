## Pneumatic Artificial Muscle Nonlinear Dynamics Analysis and SYSID
Nonlinear GNC framework for Pneumatic Artificial Muscles (PAMs). Features NLARX system identification (Sigmoid, Wavelet, idTreePartition) and robust state estimation (Kalman Filters) designed to reject complex hysteresis-induced bias and non-differentiable gradient spikes. Also contains Monte Carlo regarding Unscented Kalman Filter and Model Predictive Control. 

## Institutional Context & Academic Foundation**
This framework represents the technical implementation of research conducted at the **Rochester Institute of Technology (RIT)**.

* **Thesis Title**: *Stable Open-Loop Modeling and Estimation of McKibben Artificial Muscles*.
* **Cerficiation**: Master of Science in Mechanical Engineering (Date: August 2022 - December 2025). 
* **Abstract * Metadata** 
* **Status**: The M.S. Thesis with theories, analysis, and 15M+ sample dataset are currently under embargo pending publications in *IEEE T-RO*, *IJRR*, and *Data in Brief*

For further information pertaining the research related to thesis under RIT, please reach out to the **author** Bryan @ wwy6929@rit.edu or **Principal Investigator**, supervisor of the M.S. Thesis, Dr. Kathleen Lamkin-Kennard @ kaleme@rit.edu. 
## **Project Roadmap**
This repository is organized into three distince technical reports that follows **Input ~> Evidence ~> Decision framework** workflow. This functionally amounts to a **Guidance, Navigation, and Control (GNC)** stack-equivalent. 

1. **01-NLARX-SysID-Estimation**: Comparison of different models (NLARX models vs different Kalman Filters) and rejection of Extended Kalman Filter (EKF) and Cubature Kalman Filter (CKF) in favor of Unscented Kalman Filter

2. **02-Monte-Carlo-UKF**: (Work In Progress) Statistical verification of estimator robustness across randomized initial conditions. 

3. **03-Nonlinear-MPC**: (Work In Progress) Real-Time Tracking of Fourier-series references using the NLARX PLant Models. 

## **Licensing & Intellectual Property**

This project utilizes a **dual-licensing framework** to distinguish between functional software and technical research analysis:

* **Software & Scripts**: All MATLAB source code (.m) and supporting functions are provided under the **MIT License**.

* **Technical Analysis**: The reports, unique figure interpretations, and design-decision narratives contained in the README files are copyright © 2026 Bryan Lukehart-Yun and licensed under **CC BY-NC-ND 4.0**. 

* **Data Attribution**: The provided 10,000-sample dataset containing multiple permutations (.mat) is a series of randomized, non-representative slices **intended for architectural demonstration**.
Full high-fidelity datasets (15M+ samples) and theoretical derivations are reserved for upcoming publications in T-RO, IJRR, and Data In Brief. 

* **Future Release** The complete 15-million-sample global dataset will be published via Data in Brief; this repository will be updated with the public access links upon release. 

**Citation**: If you utilize this GNC framework or the UKF bias-rejection analysis in your work, please attribute it to this repository or the forthcoming Zenodo DOI. 