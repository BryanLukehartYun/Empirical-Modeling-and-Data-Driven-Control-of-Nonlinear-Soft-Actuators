## Pneumatic Artificial Muscle Nonlinear Dynamics Analysis and SYSID
**Nonlinear GNC framework for Pneumatic Artificial Muscles (PAMs). Features NLARX system identification (Sigmoid, Wavelet, idTreePartition) and robust state estimation (Kalman Filters) designed to reject complex hysteresis-induced bias and non-differentiable gradient spikes. Also contains Monte Carlo regarding Unscented Kalman Filter and Model Predictive Control.** 

**Preface**: Traditional industry estimators (EKF/CKF) fail on soft-actuator dynamics due to inherent hysteresis and non-differentiable gradient spikes. In this repository, a series of reports aims to create a unified workflow that models, estimates, and predicts a solution to dealing with nonlinear hysteretic actuators. 
## Core Success Metrics & Results 
* Model Fidelity - Achieved a 98.2% fitness match using Sigmoid-NLARX models, significantly outperforming standard linear approximations in capturing hysteresis drift inherent to soft actuators. 
* Bias Rejection - Successfully eliminated -7.5mm tracking bias inherent in EKF/CKF implementations by using a tuned Unscented Kalman Fulter. 
* Jacobian Diagnostics - Quantified non-differentiable gradient spikes, providing a mathematical basis for the Linearization trap that plagues and causes standard industry estimators to fail. 

## Institutional Context & Academic Foundation | Technical Expansion
This framework represents the **technical expansion and demonstration** of research established within the **BioSEL Lab** at the **Rochester Institute of Technology (RIT)**.

* **Academic Anchor**: Builds upon principles validated in my thesis and bridge the gap between Academia and the industry.  
* **Thesis Title**: *Stable Open-Loop Modelling of McKibben Muscle with Tunable
Slider*.
* **Certification**: Master of Science in Mechanical Engineering (Date: August 2022 - December 2025). 
* **Abstract & Metadata** Formal Abstract and institutional metadata available via [RIT Digital Commons - Thesis](https://repository.rit.edu/theses/12372/)
* **Status & Notice**: The M.S. Thesis with full-scale research (data, derivations, and analysis) are currently under embargo pending publications in *IEEE T-RO*, *IJRR*, and *Data in Brief*

For further information pertaining the research related to thesis under RIT, please reach out to the following authors: 
* Primary Author: Bryan Lukehart-Yun @ wwy6929@rit.edu pertaining to research collaboration or thesis. For clarification, refer to the table below if related to professional interest.  
* **Principal Investigator**: Dr. Kathleen Lamkin-Kennard, Supervisor of the M.S. Thesis, @ kaleme@rit.edu pertaining to BioSEL Lab activities and further collaboration. 

| Inquiry Type | Point of Contact | Action |
| :--- | :--- | :--- |
| **Recruitment & Professional** | Bryan Lukehart-Yun | [Email bryan.lukehartyun@gmail.com](mailto:bryan.lukehartyun@gmail.com) |
| **Technical & Repository Help** | Bryan Lukehart-Yun | Open a GitHub Issue |
| **BioSEL Research & Lab Collaboration** | Dr. Kathleen Lamkin-Kennard | [View RIT Faculty Profile](https://www.rit.edu/directory/kaleme-kathleen-lamkin-kennard) |


## **Roadmap**
This repository is organized into three distinct technical reports that follows **Input $\rightarrow$ Evidence $\rightarrow$ Decision framework**. This functionally amounts to a **Guidance, Navigation, and Control (GNC)** stack-equivalent. 

1. **01-NLARX-SysID-Estimation**: Comparison of different models (NLARX models vs different Kalman Filters) and rejection of Extended Kalman Filter (EKF) and Cubature Kalman Filter (CKF) in favor of Unscented Kalman Filter

2. **02-Monte-Carlo-UKF**: (Work In Progress) Statistical verification of estimator robustness across randomized initial conditions. 

3. **03-Nonlinear-MPC**: (Work In Progress) Real-Time Tracking of Fourier-series references using the NLARX PLant Models for Model Predictive Controls. 

4. **04-GNC-Integration**: (Planned). Integrate and expand all three scripts into a single framework and create a coherent closed-loop Model Predictive Control solution. 

5. **Notice**: Future works may expand or extend the reports here for publications (not limited to the aforementioned journals). This repository is intended to validate and serve as a sample of the work that can be extended to the Industry. 

## **Licensing & Intellectual Property**

This project utilizes a **dual-licensing framework** to distinguish between functional software and technical research analysis:

* **Software & Scripts**: All MATLAB source code (.m) and supporting functions are provided under the **MIT License**.

* **Technical Analysis**: The reports, unique figure interpretations, and design-decision narratives contained in the README files are copyright © 2026 Bryan Lukehart-Yun and licensed under **CC BY-NC-ND 4.0**. 

* **Data Attribution**: The provided 10,000-sample dataset containing multiple permutations (.mat) is a series of randomized, non-representative slices **intended for architectural demonstration**.
Full high-fidelity datasets (15M+ samples) and theoretical derivations are reserved for upcoming publications in T-RO, IJRR, and Data In Brief. 

* **Future Release** The complete 15-million-sample global dataset will be published via Data in Brief; this repository will be updated with the public access links upon release. 

**Citation**: If you utilize this GNC framework or the UKF bias-rejection analysis in your work, please attribute it to this repository or the forthcoming Zenodo DOI. 

**TL;DR: The MATLAB Code is open-source (MIT License), while the Technical Reports, Analysis, and Figures are protected intellectual property (CC BY-NC-ND 4.0).**