# **Technical Report #2 - Monte Carlo Validation of UKF Stability**

## **Overview & Data Disclaimer**
This report evaluates the statistical robustness of the state estimation framework. We subjected both the Sigmoid-NLARX and Wavelet-NLARX models to 100-run Monte Carlo Simulations downsampled to 1/20th of the sample size (500 samples) to validate the Unscented Kalman Filter (UKF) stability under randomized noise and initial conditions. 

* **Technical Analysis**: All figures and metrics are derived from high-fidelity research data (10,000 Samples) based on canonical soft actuator profiles. 
* **Licensing**: Documentation, visuals (figures), and analysis written here are licensed under **CC BY-NC-ND 4.0**. The MATLAB code are covered under MIT License. 
* **Research Integrity**: Raw batch-processing data remains under embargo pending formal publication in ***Data in Brief***. 

---

## **1. Comparative Robustness: Sigmoid vs Wavelet**
To simulate pneumatic variance and sensor noise, the estimator was subjected to randomized initial conditions and Gaussian noise injections across 100 iterations with randomized state initialization and Gaussian noise injections. 

![Figure 1](./assets/MonteCarloComparison.jpg)
*Figure 1: Monte Carlo robustness validation (N=100) for Sigmoid (Left) and Wavelet (Right) models. Gray regions represent Monte Carlo dispersions; Blue lines represent the mean estimate; Red dashed lines represent the 3σ confidence boundaries.*


* **Statistical Consistency**: Both models demonstrated 100% convergence across the test batch, with the 3σ bounds tightly containing the plant dynamics during high-frequency transitions. 
The UKF demonstrated repeatable bias rejection, maintaining a stable RMSE across the entire batch.
* **Wavelet Performnance**: The Wavelet-UKF remains a viable secondary model, showing slightly more dispersion during the intiial transient but still maintained steady-state tracking. 
* **Sigmoid Performance**: The Sigmoid-UKF exhibits consistently high RMSE stability and narrower confidence intervals, confirming its selection for the final control framework. 
* **Convergence**: 100% of runs achieved steady-state tracking within the required real-time window, validating the architecture for the upcoming MPC framework.

---

## **2 . Final Selection for Control**
While the Wavelet model is a robust estimator, the Sigmoid-NLARX was ultimately selected for Report #3 (MPC). The Sigmoid's continous gradients ensures that the numerical stability will work with the NMPC optimizer, which is critical for real-time pneumatic control. 

**Selected Model for Report #3 (MPC):**
* **Plant Model**: Sigmoid-based NLARX.
* **State Estimator**: Unscented Kalman Filter (UKF)
---

## **3. Implementation Status**
The Monte Carlo Scripts are currently undergoing final optimization and local validation. Source code for this module will be pushed to the directory following the next development cycle. 

---
