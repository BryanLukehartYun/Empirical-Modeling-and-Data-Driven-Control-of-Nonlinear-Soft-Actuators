# =============================================================================
#  unified_SYSID.py
#  PAM Nonlinear SysID — Complete Unified Pipeline
#
#  This is a consolidated, self-contained version of the full SYSID that MATLAB
#  was done in (PAM_Nonlinear_SYSIDEstimator_Core.m) as a major port. 
#  !!!IMPORTANT!!! This py file following the MATLAB counterpart is using generic weightings
#
#  Pipeline:
#    1. Load + clean + normalize (.mat file)
#    2. Fit NLARX models (Sigmoid, Wavelet, Tree)
#    3. Run Kalman filters (EKF, UKF, CKF) on each model
#    4. Print fitness / RMSE summary table
#    5. Generate and save figures
#
#  Usage: (Note this was done using uv run on my end, I cannot say with confidence that python works)
#    python unified_SYSID.py --mat CombinedPermutation_EXAMPLE_arrays.mat --perm 1
# =============================================================================

import argparse
import os
import sys
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.io.matlab import varmats_from_mat
import scipy.io
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
from filterpy.kalman import UnscentedKalmanFilter, MerweScaledSigmaPoints

matplotlib.rcParams.update({
    'font.size'       : 11,
    'axes.titlesize'  : 12,
    'axes.labelsize'  : 11,
    'legend.fontsize' : 9,
    'lines.linewidth' : 1.4,
    'figure.dpi'      : 120,
})


# =============================================================================
# SECTION 1: UTILITIES
# =============================================================================

def nlarx_state_transition(x, u_new, model):
    """NLARX state transition for Kalman Filter integration.
    Mirrors MATLAB nlarx_state_transition helper.
    State: x[0]=y_k, x[1]=y_prev, x[2]=u_prev
    Orders = [2 2 1]
    """
    y_k    = x[0]
    y_prev = x[1]
    u_prev = x[2]

    regressors = np.array([[y_k, y_prev, u_new, u_prev]])
    y_next     = model.predict(regressors).flatten()[0]

    return np.array([y_next, y_k, u_new])


def measurement_function(x):
    """h(x) for Kalman Filter. Equivalent to MATLAB h = @(x) x(1)."""
    return np.array([x[0]])


def build_regressor_matrix(y, u, n_y=2, n_u=1):
    """Build regressor matrix for NLARX fitting.
    Mirrors MATLAB orders = [n_y, n_y, n_u].
    For [2,2,1]: regressors = [y(k-1), y(k-2), u(k-1)]

    Returns
    -------
    X        : np.ndarray, shape (N - max_lag, n_y + n_u)
    y_target : np.ndarray, shape (N - max_lag,)
    """
    max_lag = max(n_y, n_u)
    N       = len(y)
    rows    = []

    for k in range(max_lag, N):
        row = [y[k - lag] for lag in range(1, n_y + 1)]
        row += [u[k - lag] for lag in range(1, n_u + 1)]
        rows.append(row)

    return np.array(rows), y[max_lag:]


def compute_rmse(y_true, y_pred):
    """Root Mean Square Error in original units (mm)."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def compute_fitness(y_true, y_pred):
    """MATLAB-equivalent fitness percentage.
    fit = 100 * (1 - norm(y_true - y_pred) / norm(y_true - mean(y_true)))
    """
    num   = np.linalg.norm(y_true - y_pred)
    denom = np.linalg.norm(y_true - np.mean(y_true))

    if denom == 0:
        return 0.0

    return max(100.0 * (1.0 - num / denom), 0.0)


def print_model_summary(name, fitness, rmse):
    """Formatted model result print. Mirrors MATLAB fprintf style."""
    print(f'  [{name}] Fitness: {fitness:.2f}%  |  RMSE: {rmse:.4f} mm')


# =============================================================================
# SECTION 2: DATA LOADING
# =============================================================================

def load_permutation(filepath: str, permutation: int = 3) -> dict:
    with open(filepath, 'rb') as f:
        vmats = varmats_from_mat(f)

    n_perms = len(vmats)
    assert 1 <= permutation <= n_perms, \
        f"Permutation must be 1–{n_perms} (file has {n_perms} permutations)."

    idx = permutation - 1
    name, mat_file = vmats[idx]
    data = scipy.io.loadmat(mat_file, simplify_cells=True)

    # grab whatever key exists
    keys = [k for k in data.keys() if not k.startswith('_')]
    perm = data[keys[0]]

    print(f'Loaded variable index {idx}, keys found: {keys}')
    print(f'Perm type: {type(perm)}')
    print(f'Perm fields: {perm.dtype.names if hasattr(perm, "dtype") else dir(perm)}')

    return {
        'Pressure' : np.array(perm['Pressure']).flatten(),
        'Length'   : np.array(perm['Length']).flatten(),  # raw length values
        'Time'     : np.array(perm['Time']).flatten(),
    }


def clean_nan(data: dict) -> dict:
    """
    Remove NaN entries from all channels simultaneously.
    Mirrors MATLAB: valid_idx = ~isnan(P) & ~isnan(L)

    Parameters
    ----------
    data : dict
        Output of load_permutation().

    Returns
    -------
    dict with NaN rows removed across all channels.
    """
    P = data['Pressure']
    L = data['Length']
    T = data['Time']

    valid_idx = ~np.isnan(P) & ~np.isnan(L)

    n_removed = np.sum(~valid_idx)
    if n_removed > 0:
        print(f'[clean_nan] Removed {n_removed} NaN samples.')

    return {
        'Pressure' : P[valid_idx],
        'Length'   : L[valid_idx],
        'Time'     : T[valid_idx],
    }


def normalize_minmax(data: dict) -> tuple:
    """
    Apply Min-Max normalization to Pressure and Length.
    Vital for nonlinear solvers — mirrors MATLAB normalization block.

    Parameters
    ----------
    data : dict
        Cleaned data dict from clean_nan().

    Returns
    -------
    norm_data : dict
        Normalized Pressure and Length (0 to 1 range), plus raw Time.
    scale_params : dict
        Min/max values needed to denormalize outputs later.
        Keys: 'P_min', 'P_max', 'L_min', 'L_max'
    """
    P = data['Pressure']
    L = data['Length']

    P_min, P_max = P.min(), P.max()
    L_min, L_max = L.min(), L.max()

    P_norm = (P - P_min) / (P_max - P_min)
    L_norm = (L - L_min) / (L_max - L_min)

    norm_data = {
        'Pressure' : P_norm,
        'Length'   : L_norm,
        'Time'     : data['Time'],
    }

    scale_params = {
        'P_min' : P_min,
        'P_max' : P_max,
        'L_min' : L_min,
        'L_max' : L_max,
    }

    return norm_data, scale_params


def denormalize(y_norm: np.ndarray, scale_params: dict) -> np.ndarray:
    """
    Reverse Min-Max normalization on Length output.
    Use this to convert estimator outputs back to mm.

    Parameters
    ----------
    y_norm : np.ndarray
        Normalized length estimates.
    scale_params : dict
        Scale params from normalize_minmax().

    Returns
    -------
    np.ndarray in original mm scale.
    """
    return y_norm * (scale_params['L_max'] - scale_params['L_min']) + scale_params['L_min']


def load_and_prepare(filepath: str, permutation: int = 3) -> tuple:
    """
    Full pipeline: load → clean → normalize.
    Convenience wrapper for main.py.

    Parameters
    ----------
    filepath : str
        Path to .mat file.
    permutation : int
        Permutation index to load (1-based; file may have 1–8 permutations).

    Returns
    -------
    raw_data    : dict — cleaned, unnormalized (Pressure mm/kPa, Length mm, Time s)
    norm_data   : dict — normalized (0-1 range)
    scale_params: dict — min/max for denormalization
    """
    raw      = load_permutation(filepath, permutation)
    cleaned  = clean_nan(raw)
    norm_data, scale_params = normalize_minmax(cleaned)

    print(f'[load_and_prepare] Permutation {permutation} loaded.')
    print(f'  Samples : {len(cleaned["Pressure"])}')
    print(f'  Pressure: [{scale_params["P_min"]:.2f}, {scale_params["P_max"]:.2f}] kPa')
    print(f'  Length  : [{scale_params["L_min"]:.2f}, {scale_params["L_max"]:.2f}] mm')

    return cleaned, norm_data, scale_params


# =============================================================================
# SECTION 3: NLARX MODELS
# =============================================================================

def _build_training_data(y_norm: np.ndarray, u_norm: np.ndarray,
                          n_y: int = 2, n_u: int = 2):
    """
    Build 4-feature training regressor matrix for NLARX orders [na=2, nb=2, nk=1].

    Regressor at step k: [y(k-1), y(k-2), u(k-1), u(k-2)] → target y(k)

    This is NOT the same as utils.build_regressor_matrix (which uses n_u=1).
    The 4-feature layout must match utils.nlarx_state_transition which expects
    regressors = [y_k, y_prev, u_new, u_prev].

    Parameters
    ----------
    y_norm : (N,) normalized length signal
    u_norm : (N,) normalized pressure signal

    Returns
    -------
    X        : (N - max_lag, 4)
    y_target : (N - max_lag,)
    """
    max_lag = max(n_y, n_u)
    N = len(y_norm)
    X = []
    y_target = []
    for k in range(max_lag, N):
        row = [y_norm[k - 1], y_norm[k - 2], u_norm[k - 1], u_norm[k - 2]]
        X.append(row)
        y_target.append(y_norm[k])
    return np.array(X), np.array(y_target)


class _NLARXBase:
    """
    Base NLARX wrapper. Subclasses set self._estimator to a sklearn estimator.
    The predict interface is sklearn-compatible: X shape (n, 4).
    """

    _estimator = None   # set by subclass
    _fitted: bool = False

    def fit(self, u_norm: np.ndarray, y_norm: np.ndarray):
        """
        Train on normalized pressure/length signals (one-step prediction objective).

        Parameters
        ----------
        u_norm : (N,) pressure, range [0, 1]
        y_norm : (N,) length, range [0, 1]
        """
        X, y_t = _build_training_data(y_norm, u_norm)
        self._estimator.fit(X, y_t)
        self._fitted = True
        return self

    def fit_for_simulation(self, u_norm: np.ndarray, y_norm: np.ndarray,
                           n_rounds: int = 3,
                           sim_fraction: float = 0.5,
                           min_fitness_to_mix: float = 20.0):
        """
        Simulation-focused training — mirrors MATLAB nlarx Focus='simulation'.

        MATLAB trains the network weights to minimize multi-step simulation
        error, not just one-step prediction error.  This iterative approach
        approximates that:
          1. Fit on true one-step regressors (standard).
          2. Simulate free-run to get y_sim (includes own prediction errors).
          3. If simulation fitness > min_fitness_to_mix, add simulated
             regressors to training data (gives the model experience with
             its own errors so it can self-correct).
          4. Retrain on mixed true + simulated regressors (fresh, no warm_start
             to avoid adam momentum instability with new data distribution).
          5. Repeat n_rounds times.

        Parameters
        ----------
        u_norm              : (N,) normalized pressure
        y_norm              : (N,) normalized length
        n_rounds            : refinement rounds after initial fit
        sim_fraction        : fraction of simulated regressors to mix in
        min_fitness_to_mix  : skip simulation mixing if free-run fitness is
                              below this threshold — avoids training on
                              divergent garbage trajectories
        """
        # Round 0: standard one-step fit
        X_true, y_true_t = _build_training_data(y_norm, u_norm)
        self._estimator.fit(X_true, y_true_t)
        self._fitted = True

        rng = np.random.default_rng(seed=0)
        for r in range(n_rounds):
            y_sim = self.simulate(u_norm, y_norm)
            sim_fitness = compute_fitness(y_norm, y_sim)

            # Only mix in simulated data if simulation is not completely broken
            if sim_fitness < min_fitness_to_mix:
                break

            X_sim, y_sim_t = _build_training_data(y_sim, u_norm)
            n_mix = int(len(X_sim) * sim_fraction)
            idx = rng.choice(len(X_sim), n_mix, replace=False)

            X_mixed = np.vstack([X_true, X_sim[idx]])
            y_mixed = np.concatenate([y_true_t, y_sim_t[idx]])

            # Fresh fit — avoids adam momentum instability from warm_start
            # when data distribution changes significantly between rounds
            self._estimator.fit(X_mixed, y_mixed)

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Single-step prediction. Mirrors MATLAB's evaluate(net, regressors).

        Parameters
        ----------
        X : (n, 4) array — each row is [y_k, y_prev, u_new, u_prev]

        Returns
        -------
        (n,) array of predicted y_next values
        """
        return self._estimator.predict(X)

    def simulate(self, u_norm: np.ndarray, y_norm: np.ndarray) -> np.ndarray:
        """
        Free-run multi-step simulation. Mirrors MATLAB compare(data, sys_nl, ...).

        At each step k >= 2, predicted y_hat(k) is fed back as y_sim(k-1)
        in the next regressor, so errors accumulate (true generalization test).

        Parameters
        ----------
        u_norm : (N,) normalized pressure
        y_norm : (N,) normalized length (used only for initial conditions)

        Returns
        -------
        y_sim  : (N,) simulated normalized length
        """
        N = len(u_norm)
        y_sim = np.zeros(N)
        y_sim[0] = y_norm[0]
        y_sim[1] = y_norm[1]

        for k in range(2, N):
            reg = np.array([[y_sim[k - 1], y_sim[k - 2],
                             u_norm[k - 1], u_norm[k - 2]]])
            y_hat = self._estimator.predict(reg)[0]
            y_sim[k] = y_hat

        return y_sim

    def score(self, u_norm: np.ndarray, y_norm: np.ndarray):
        """
        Run simulate() and compute MATLAB-equivalent fitness + RMSE.

        Returns
        -------
        fitness : float  (%)
        rmse    : float  (normalized units; denormalize via scale_params for mm)
        y_sim   : (N,) array
        """
        y_sim = self.simulate(u_norm, y_norm)
        fitness = compute_fitness(y_norm, y_sim)
        rmse = compute_rmse(y_norm, y_sim)
        return fitness, rmse, y_sim


class SigmoidNLARX(_NLARXBase):
    """
    Single hidden-layer MLP with logistic (sigmoid) activation.

    This is the direct Python equivalent of MATLAB's idSigmoidNetwork:
      - 10 hidden units (matching MATLAB NumberOfUnits=10)
      - Logistic activation = sigmoid function
      - adam solver
      - L2 regularization alpha=1e-4

    Target: primary model matching MATLAB ~93-96% fitness.
    """

    def __init__(self):
        # Generic sigmoid MLP for NLARX identification.
        self._estimator = MLPRegressor(
            hidden_layer_sizes=(10,),
            activation='logistic',
            solver='adam',
            learning_rate_init=0.001,
            alpha=1e-4,
            max_iter=5000,
            n_iter_no_change=50,
            tol=1e-7,
            random_state=None,
        )
        self._fitted = False


class WaveletNLARX(_NLARXBase):
    """
    Single hidden-layer MLP with hyperbolic tangent activation.

    MATLAB's idWaveletNetwork uses a sum of translated/dilated wavelets.
    tanh is a smooth, symmetric, zero-mean activation — the same building
    block used in wavelet neural networks (Morlet-style).  This is the
    closest sklearn approximation without implementing a full wavelet basis.

    - 20 hidden units (tanh benefits from more units)
    - tanh activation
    - adam solver
    """

    def __init__(self):
        # Generic wavelet-like MLP using tanh activation.
        self._estimator = MLPRegressor(
            hidden_layer_sizes=(20,),
            activation='tanh',
            solver='adam',
            learning_rate_init=0.001,
            alpha=1e-4,
            max_iter=5000,
            n_iter_no_change=50,
            tol=1e-7,
            random_state=None,
        )
        self._fitted = False


class TreeNLARX(_NLARXBase):
    """
    Gradient-boosted regression trees.

    MATLAB's idTreePartition produces a piecewise-constant regression tree.
    GradientBoostingRegressor approximates the same piecewise behavior with
    smoother gradients, which helps Kalman filter Jacobian stability.
    """

    def __init__(self):
        # Generic tree-based NLARX using gradient boosting.
        self._estimator = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=None,
        )
        self._fitted = False


def fit_all_models(u_norm: np.ndarray, y_norm: np.ndarray,
                   verbose: bool = True) -> dict:
    """
    Train SigmoidNLARX, WaveletNLARX, and TreeNLARX.

    Returns
    -------
    results : dict keyed by model name, each value:
        {
            'model'  : fitted _NLARXBase (Kalman-compatible),
            'fitness': float (%),
            'rmse'   : float (normalized),
            'y_sim'  : (N,) simulated output,
        }
    """
    if verbose:
        print("\n[nlarx_models] Fitting NLARX models...")
        print(f"  Training samples : {len(y_norm)}")

    models = {
        'Sigmoid': SigmoidNLARX(),
        'Wavelet': WaveletNLARX(),
        'Tree'   : TreeNLARX(),
    }

    results = {}
    for name, model in models.items():
        if verbose:
            print(f"  Fitting {name}...", end=' ', flush=True)
        model.fit(u_norm, y_norm)
        fitness, rmse, y_sim = model.score(u_norm, y_norm)
        if verbose:
            print(f"Fitness: {fitness:.2f}%  RMSE: {rmse:.5f}")
        results[name] = {
            'model'  : model,
            'fitness': fitness,
            'rmse'   : rmse,
            'y_sim'  : y_sim,
        }

    if verbose:
        print()

    return results


# =============================================================================
# SECTION 4: KALMAN FILTERS
# =============================================================================

# Generic Kalman filter noise parameters
_Q_EKF = np.diag([1e-4, 1e-4, 1e-4])
_R_EKF = np.array([[1e-3]])

_Q_UKF = np.diag([1e-4, 1e-4, 1e-4])
_R_UKF = np.array([[1e-3]])

_Q_CKF = np.diag([1e-4, 1e-4, 1e-4])
_R_CKF = np.array([[1e-3]])

_H = np.array([[1.0, 0.0, 0.0]])   # measurement matrix: observe x[0]
_DIM_X = 3
_DIM_Z = 1


def _numerical_jacobian(f, x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """
    Central-difference Jacobian of vector-valued f at x.
    Used by EKF to linearize the state transition.

    Returns J shape (dim_x, dim_x).
    """
    n = len(x)
    fx = f(x)
    J = np.zeros((len(fx), n))
    for i in range(n):
        x_pos = x.copy()
        x_neg = x.copy()
        x_pos[i] += eps
        x_neg[i] -= eps
        J[:, i] = (f(x_pos) - f(x_neg)) / (2.0 * eps)
    return J


def run_ekf(model, u_norm: np.ndarray, y_norm: np.ndarray,
            Q: np.ndarray = None, R: np.ndarray = None) -> np.ndarray:
    """
    Run Extended Kalman Filter on normalized data.

    Loop order: correct(y_norm[k]) → record → predict(u_norm[k])
    Mirrors MATLAB: correct(obj_ekf, y_norm(k)) then predict(obj_ekf, u_norm(k))

    Parameters
    ----------
    model   : fitted _NLARXBase instance (SigmoidNLARX / WaveletNLARX / TreeNLARX)
    u_norm  : (N,) normalized pressure
    y_norm  : (N,) normalized length (measurements)
    Q       : (3, 3) process noise covariance — default EKF tuning
    R       : (1, 1) measurement noise covariance — default EKF tuning

    Returns
    -------
    y_est : (N,) filtered length estimate (normalized)
    """
    if Q is None:
        Q = _Q_EKF
    if R is None:
        R = _R_EKF

    N = len(y_norm)
    y_est = np.zeros(N)

    # Initial state: [y(0), y(0), u(0)]
    x = np.array([y_norm[0], y_norm[0], u_norm[0]])
    P = np.eye(_DIM_X) * 0.01

    R_scalar = float(R.flatten()[0])

    for k in range(N):
        # ---- CORRECT step (measurement update) ----
        z = y_norm[k]
        # Innovation: scalar h(x) = x[0]
        innov = z - x[0]
        # S = H P H^T + R  (scalar)
        S = float(_H @ P @ _H.T) + R_scalar
        # Kalman gain (3,1)
        K = (P @ _H.T) / S
        x = x + K.flatten() * innov
        P = (np.eye(_DIM_X) - K @ _H) @ P
        # Symmetrize P to prevent numerical drift
        P = 0.5 * (P + P.T)

        y_est[k] = x[0]

        # ---- PREDICT step (state propagation) ----
        u_k = u_norm[k]
        # Nonlinear state propagation
        x_next = nlarx_state_transition(x, u_k, model)
        # Linearize f at current x for covariance propagation
        f_at_x = lambda xv: nlarx_state_transition(xv, u_k, model)
        F = _numerical_jacobian(f_at_x, x)
        # Propagate covariance with linearized F
        P = F @ P @ F.T + Q
        P = 0.5 * (P + P.T)
        x = x_next

    return y_est


def run_ukf(model, u_norm: np.ndarray, y_norm: np.ndarray,
            Q: np.ndarray = None, R: np.ndarray = None,
            Ts: float = 0.01) -> np.ndarray:
    """
    Run Unscented Kalman Filter on normalized data via filterpy.

    No Jacobian required — sigma points propagate through the true nonlinear f.
    MerweScaledSigmaPoints with alpha=1e-3, beta=2, kappa=0 (standard UKF).

    Parameters
    ----------
    model   : fitted _NLARXBase instance
    u_norm  : (N,) normalized pressure
    y_norm  : (N,) normalized length
    Q       : (3, 3) process noise — default UKF tuning
    R       : (1, 1) measurement noise — default UKF tuning
    Ts      : sampling period (s), default 0.01 (100 Hz)

    Returns
    -------
    y_est : (N,) filtered length estimate (normalized)
    """
    if Q is None:
        Q = _Q_UKF
    if R is None:
        R = _R_UKF

    N = len(y_norm)
    y_est = np.zeros(N)

    # Build state transition closure — u_new passed as kwarg at predict time
    def fx(x, dt, u_new):
        return nlarx_state_transition(x, u_new, model)

    def hx(x):
        return np.array([x[0]])

    points = MerweScaledSigmaPoints(
        n=_DIM_X, alpha=1e-3, beta=2.0, kappa=0.0
    )

    ukf = UnscentedKalmanFilter(
        dim_x=_DIM_X, dim_z=_DIM_Z,
        dt=Ts, fx=fx, hx=hx,
        points=points,
    )

    ukf.x = np.array([y_norm[0], y_norm[0], u_norm[0]])
    ukf.P = np.eye(_DIM_X) * 0.01
    ukf.Q = Q
    ukf.R = R
    # Pre-seed sigma points so the first update() has correct K (not K≈0 from zeros)
    ukf.sigmas_f = ukf.points_fn.sigma_points(ukf.x, ukf.P)

    for k in range(N):
        # ---- CORRECT step ----
        ukf.update(z=np.array([y_norm[k]]))
        y_est[k] = ukf.x[0]

        # ---- PREDICT step ----
        ukf.predict(u_new=u_norm[k])

    return y_est


def _ckf_correct(x: np.ndarray, P: np.ndarray,
                 z: float, R_scalar: float):
    """
    CKF measurement update. h(x) = x[0] (scalar observation).

    Returns updated (x, P).
    """
    n = len(x)
    N_pts = 2 * n
    w = 1.0 / N_pts

    # Cholesky of n*P for cubature points
    try:
        S_chol = np.linalg.cholesky(n * P)
    except np.linalg.LinAlgError:
        # Regularize if P is not positive definite
        P_reg = P + np.eye(n) * 1e-8
        S_chol = np.linalg.cholesky(n * P_reg)

    # Cubature points (2n of them)
    sigmas = np.zeros((N_pts, n))
    for i in range(n):
        sigmas[i]     = x + S_chol[:, i]
        sigmas[n + i] = x - S_chol[:, i]

    # Propagate through h (linear here: h = x[0])
    z_pts = sigmas[:, 0]          # shape (2n,)
    z_pred = w * np.sum(z_pts)   # predicted measurement

    # Innovation covariance and cross-covariance
    S_z = w * np.sum((z_pts - z_pred) ** 2) + R_scalar
    Pxz = w * sum(
        np.outer(sigmas[i] - x, z_pts[i] - z_pred)
        for i in range(N_pts)
    )

    K = Pxz / S_z                      # Kalman gain (3, 1)
    x_upd = x + K.flatten() * (z - z_pred)
    P_upd = P - S_z * (K @ K.T)
    P_upd = 0.5 * (P_upd + P_upd.T)

    return x_upd, P_upd


def _ckf_predict(x: np.ndarray, P: np.ndarray,
                 u_k: float, model, Q: np.ndarray):
    """
    CKF time update (predict). Propagates sigma points through nonlinear f.

    Returns predicted (x, P).
    """
    n = len(x)
    N_pts = 2 * n
    w = 1.0 / N_pts

    try:
        S_chol = np.linalg.cholesky(n * P)
    except np.linalg.LinAlgError:
        P_reg = P + np.eye(n) * 1e-8
        S_chol = np.linalg.cholesky(n * P_reg)

    sigmas = np.zeros((N_pts, n))
    for i in range(n):
        sigmas[i]     = x + S_chol[:, i]
        sigmas[n + i] = x - S_chol[:, i]

    # Propagate each cubature point through nonlinear f
    sigmas_f = np.array([
        nlarx_state_transition(sigmas[i], u_k, model) for i in range(N_pts)
    ])

    x_pred = w * np.sum(sigmas_f, axis=0)
    P_pred = w * sum(
        np.outer(sigmas_f[i] - x_pred, sigmas_f[i] - x_pred)
        for i in range(N_pts)
    ) + Q
    P_pred = 0.5 * (P_pred + P_pred.T)

    return x_pred, P_pred


def run_ckf(model, u_norm: np.ndarray, y_norm: np.ndarray,
            Q: np.ndarray = None, R: np.ndarray = None) -> np.ndarray:
    """
    Run Cubature Kalman Filter on normalized data.

    Implements the CKF (Arasaratnam & Haykin, 2009) with 2n cubature points
    and uniform weights 1/(2n). Mirrors MATLAB trackingCKF behavior.

    Parameters
    ----------
    model   : fitted _NLARXBase instance
    u_norm  : (N,) normalized pressure
    y_norm  : (N,) normalized length
    Q       : (3, 3) process noise — default CKF tuning
    R       : (1, 1) measurement noise — default CKF tuning

    Returns
    -------
    y_est : (N,) filtered length estimate (normalized)
    """
    if Q is None:
        Q = _Q_CKF
    if R is None:
        R = _R_CKF

    N = len(y_norm)
    y_est = np.zeros(N)

    x = np.array([y_norm[0], y_norm[0], u_norm[0]])
    P = np.eye(_DIM_X) * 0.01
    R_scalar = float(R.flatten()[0])

    for k in range(N):
        # ---- CORRECT step ----
        x, P = _ckf_correct(x, P, z=float(y_norm[k]), R_scalar=R_scalar)
        y_est[k] = x[0]

        # ---- PREDICT step ----
        x, P = _ckf_predict(x, P, u_k=float(u_norm[k]), model=model, Q=Q)

    return y_est


def run_all_filters(model, u_norm: np.ndarray, y_norm: np.ndarray,
                    model_name: str = '',
                    verbose: bool = True) -> dict:
    """
    Run EKF, UKF, and CKF on a single NLARX model.

    Parameters
    ----------
    model      : fitted _NLARXBase instance
    u_norm     : (N,) normalized pressure
    y_norm     : (N,) normalized length
    model_name : str label for printing
    verbose    : print fitness per filter

    Returns
    -------
    dict with keys 'EKF', 'UKF', 'CKF', each containing:
        {
            'y_est'  : (N,) normalized filtered estimate,
            'fitness': float (%),
            'rmse'   : float (normalized),
        }
    """
    if verbose and model_name:
        print(f"\n[kalman_filters] Running filters for model: {model_name}")

    results = {}
    for name, runner in [('EKF', run_ekf), ('UKF', run_ukf), ('CKF', run_ckf)]:
        if verbose:
            print(f"  Running {name}...", end=' ', flush=True)
        y_est = runner(model, u_norm, y_norm)
        fitness = compute_fitness(y_norm, y_est)
        rmse = compute_rmse(y_norm, y_est)
        if verbose:
            print(f"Fitness: {fitness:.2f}%  RMSE: {rmse:.5f}")
        results[name] = {
            'y_est'  : y_est,
            'fitness': fitness,
            'rmse'   : rmse,
        }

    return results


def run_all_models_all_filters(nlarx_results: dict,
                                u_norm: np.ndarray,
                                y_norm: np.ndarray,
                                verbose: bool = True) -> dict:
    """
    Run all three filters on all Kalman-compatible NLARX models.

    Parameters
    ----------
    nlarx_results : output of nlarx_models.fit_all_models()
    u_norm        : (N,) normalized pressure
    y_norm        : (N,) normalized length

    Returns
    -------
    filter_results : nested dict — filter_results[model_name][filter_name]
                     each contains {'y_est', 'fitness', 'rmse'}

    Example
    -------
    filter_results['Sigmoid']['UKF']['y_est']  →  np.ndarray
    """
    kalman_models = {
        k: v for k, v in nlarx_results.items()
        if k in ('Sigmoid', 'Wavelet', 'Tree')
    }

    filter_results = {}
    for model_name, result in kalman_models.items():
        filter_results[model_name] = run_all_filters(
            model=result['model'],
            u_norm=u_norm,
            y_norm=y_norm,
            model_name=model_name,
            verbose=verbose,
        )

    return filter_results


# =============================================================================
# SECTION 5: PLOTTING
# =============================================================================

COLORS = {
    'measured' : '#1f77b4',
    'Sigmoid'  : '#ff7f0e',
    'Wavelet'  : '#2ca02c',
    'Tree'     : '#9467bd',
    'EKF'      : '#e377c2',
    'UKF'      : '#17becf',
    'CKF'      : '#bcbd22',
}


def _denorm_length(y_norm, scale):
    return y_norm * (scale['L_max'] - scale['L_min']) + scale['L_min']


def _denorm_pressure(u_norm, scale):
    return u_norm * (scale['P_max'] - scale['P_min']) + scale['P_min']


def _fig_path(perm_dir: str, prefix: str, name: str) -> str:
    return os.path.join(perm_dir, f'{prefix}{name}')


def plot_fig1_raw_data(raw, norm, scale, perm_dir, prefix, show=False):
    T = norm['Time']
    P = _denorm_pressure(norm['Pressure'], scale)
    L = _denorm_length(norm['Length'], scale)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    fig.suptitle('Figure 1 — PAM Raw Identification Data', fontweight='bold')

    ax1.plot(T, P, color=COLORS['measured'], lw=1.2)
    ax1.set_ylabel('Pressure (kPa)')
    ax1.set_title('Input: Pressure')
    ax1.grid(True, alpha=0.35)

    ax2.plot(T, L, color=COLORS['measured'], lw=1.2)
    ax2.set_ylabel('Contraction (mm)')
    ax2.set_xlabel('Time (s)')
    ax2.set_title('Output: Length Contraction')
    ax2.grid(True, alpha=0.35)

    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig1_raw_data.png')
    fig.savefig(path, bbox_inches='tight')
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_fig2_hysteresis(norm, scale, perm_dir, prefix, show=False):
    """
    Raw PAM hysteresis: Length (mm) vs Pressure (kPa) as a plain line.
    No colorbar — the loop shape itself shows loading/unloading arms.
    """
    P = _denorm_pressure(norm['Pressure'], scale)
    L = _denorm_length(norm['Length'], scale)

    fig, ax = plt.subplots(figsize=(7, 6))
    fig.suptitle('Figure 2 — PAM Hysteresis Loop', fontweight='bold')

    ax.plot(P, L, color=COLORS['measured'], lw=0.8, alpha=0.75)

    ax.set_xlabel('Pressure (kPa)')
    ax.set_ylabel('Contraction (mm)')
    ax.set_title('Measured: Length vs Pressure')
    ax.grid(True, alpha=0.35)

    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig2_hysteresis.png')
    fig.savefig(path, bbox_inches='tight', dpi=150)
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_fig3_nlarx_comparison(norm, scale, nlarx_results, perm_dir, prefix,
                                show=False):
    T      = norm['Time']
    L_meas = _denorm_length(norm['Length'], scale)

    plot_order = [k for k in ('Sigmoid', 'Wavelet', 'Tree')
                  if k in nlarx_results and nlarx_results[k]['y_sim'] is not None]

    n_models = len(plot_order)
    if n_models == 0:
        print('  [Fig 3] No models to plot, skipping.')
        return None

    fig, axes = plt.subplots(n_models, 1, figsize=(11, 3.5 * n_models),
                             sharex=True)
    if n_models == 1:
        axes = [axes]

    fig.suptitle('Figure 3 — NLARX Open-Loop Simulation Comparison',
                 fontweight='bold')

    for ax, name in zip(axes, plot_order):
        r = nlarx_results[name]
        L_sim   = _denorm_length(r['y_sim'], scale)
        fitness = r['fitness']
        rmse_mm = r['rmse'] * (scale['L_max'] - scale['L_min'])

        ax.plot(T, L_meas, color=COLORS['measured'], lw=1.2,
                label='Measured', zorder=3)
        ax.plot(T, L_sim, color=COLORS[name], lw=1.2, ls='--',
                label=f'{name}  (fit={fitness:.1f}%  RMSE={rmse_mm:.2f} mm)',
                zorder=2)

        ax.set_ylabel('Contraction (mm)')
        ax.set_title(f'{name} NLARX — Open-Loop Simulation')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.35)

    axes[-1].set_xlabel('Time (s)')
    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig3_nlarx_comparison.png')
    fig.savefig(path, bbox_inches='tight')
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_fig4_kalman_comparison(norm, scale, filter_results, perm_dir, prefix,
                                 show=False):
    T       = norm['Time']
    L_meas  = _denorm_length(norm['Length'], scale)
    L_range = scale['L_max'] - scale['L_min']

    model_names = list(filter_results.keys())
    n_models    = len(model_names)

    fig, axes = plt.subplots(n_models, 1, figsize=(12, 4 * n_models),
                             sharex=True)
    if n_models == 1:
        axes = [axes]

    fig.suptitle('Figure 4 — Kalman Filter Estimates (EKF / UKF / CKF)',
                 fontweight='bold')

    filt_style = {
        'EKF': dict(color=COLORS['EKF'], ls='-.', lw=1.2),
        'UKF': dict(color=COLORS['UKF'], ls='-',  lw=1.5),
        'CKF': dict(color=COLORS['CKF'], ls=':',  lw=1.2),
    }

    for ax, model_name in zip(axes, model_names):
        ax.plot(T, L_meas, color=COLORS['measured'], lw=1.0,
                alpha=0.7, label='Measured', zorder=2)

        for filt_name, res in filter_results[model_name].items():
            L_est   = _denorm_length(res['y_est'], scale)
            fitness = res['fitness']
            rmse_mm = res['rmse'] * L_range
            style   = filt_style.get(filt_name, dict(color='grey', ls='-', lw=1.2))
            ax.plot(T, L_est,
                    label=f'{filt_name}  fit={fitness:.1f}%  RMSE={rmse_mm:.3f} mm',
                    zorder=3, **style)

        ax.set_ylabel('Contraction (mm)')
        ax.set_title(f'{model_name} Model — Kalman Filter Estimates')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.35)

    axes[-1].set_xlabel('Time (s)')
    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig4_kalman_comparison.png')
    fig.savefig(path, bbox_inches='tight')
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_fig5_kalman_hysteresis(norm, scale, filter_results, perm_dir, prefix,
                                 show=False):
    P_meas = _denorm_pressure(norm['Pressure'], scale)
    L_meas = _denorm_length(norm['Length'], scale)

    fig, ax = plt.subplots(figsize=(8, 7))
    fig.suptitle('Figure 5 — Hysteresis Loop: UKF Estimates vs Measured',
                 fontweight='bold')

    ax.plot(P_meas, L_meas, color=COLORS['measured'], lw=1.0, alpha=0.4,
            label='Measured', zorder=1)

    for model_name, filters in filter_results.items():
        if 'UKF' not in filters:
            continue
        res     = filters['UKF']
        L_est   = _denorm_length(res['y_est'], scale)
        fitness = res['fitness']
        color   = COLORS.get(model_name, 'grey')
        ax.plot(P_meas, L_est, color=color, lw=1.5, alpha=0.85,
                label=f'UKF/{model_name}  fit={fitness:.1f}%', zorder=2)

    ax.set_xlabel('Pressure (kPa)')
    ax.set_ylabel('Contraction (mm)')
    ax.set_title('PAM Hysteresis: UKF State Estimates')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.35)

    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig5_kalman_hysteresis.png')
    fig.savefig(path, bbox_inches='tight', dpi=150)
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_fig6_jacobian_proxy(norm, scale, nlarx_results, perm_dir, prefix,
                              show=False):
    """
    Plots d(Length)/dt for each NLARX model via finite differences.

    The EKF must linearize the nonlinear function at every step using a
    Jacobian. Where this gradient is discontinuous or wildly varying (as
    seen in Wavelet and TreePartition), the linear approximation breaks
    down and the EKF diverges or tracks poorly. The UKF/CKF don't rely
    on this approximation, which is why they outperform EKF here.
    """
    T  = norm['Time']
    Ts = float(T[1] - T[0])          # sample interval (s)

    plot_order = [k for k in ('Sigmoid', 'Wavelet', 'Tree')
                  if k in nlarx_results and nlarx_results[k]['y_sim'] is not None]

    if not plot_order:
        print('  [Fig 6] No models to plot, skipping.')
        return None

    line_styles = {'Sigmoid': ('r', '-'),  'Wavelet': ('b', '--'),
                   'Tree':    ('g', '-.')}

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.suptitle('Figure 6 — Gradient (Jacobian Proxy) of NLARX Functions',
                 fontweight='bold')

    for name in plot_order:
        y_sim = _denorm_length(nlarx_results[name]['y_sim'], scale)
        dy    = np.diff(y_sim.ravel()) / Ts          # mm/s
        t_mid = T[:len(dy)]
        color, ls = line_styles[name]
        ax.plot(t_mid, dy, color=color, ls=ls, lw=1.3, label=name)

    ax.set_xlabel('Time (s)')
    ax.set_ylabel('d(Length)/dt  (mm/s)')
    ax.set_title('Discontinuous / high-variance gradients → EKF linearization breaks down')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.35)

    fig.tight_layout()
    path = _fig_path(perm_dir, prefix, 'fig6_jacobian_proxy.png')
    fig.savefig(path, bbox_inches='tight')
    print(f'  Saved: {path}')
    if show:
        plt.show()
    plt.close(fig)
    return fig


def plot_all(raw, norm, scale, nlarx_results, filter_results,
             permutation: int = 3, show: bool = False):
    """Generate and save all 6 figures into figures/permutation{N}/."""
    _here = os.path.dirname(os.path.abspath(__file__))
    perm_dir = os.path.join(_here, 'figures', f'permutation{permutation}')
    os.makedirs(perm_dir, exist_ok=True)
    prefix = f'perm{permutation}_'

    print('\n' + '=' * 55)
    print(f'  Generating figures → {perm_dir}/')
    print('=' * 55)
    plot_fig1_raw_data(raw, norm, scale, perm_dir, prefix, show=show)
    plot_fig2_hysteresis(norm, scale, perm_dir, prefix, show=show)
    plot_fig3_nlarx_comparison(norm, scale, nlarx_results, perm_dir, prefix,
                                show=show)
    plot_fig4_kalman_comparison(norm, scale, filter_results, perm_dir, prefix,
                                 show=show)
    plot_fig5_kalman_hysteresis(norm, scale, filter_results, perm_dir, prefix,
                                 show=show)
    plot_fig6_jacobian_proxy(norm, scale, nlarx_results, perm_dir, prefix,
                              show=show)
    print(f'  Done — {perm_dir}/')


# =============================================================================
# SECTION 6: MAIN PIPELINE
# =============================================================================

def _print_summary(nlarx_results: dict, filter_results: dict,
                   scale_params: dict):
    """Print a formatted results table in real units (mm)."""
    L_range = scale_params['L_max'] - scale_params['L_min']

    print('\n' + '=' * 65)
    print('  NLARX MODEL FITNESS (simulation, normalized space)')
    print('=' * 65)
    for name, r in nlarx_results.items():
        if r['fitness'] is not None:
            rmse_mm = r['rmse'] * L_range
            print_model_summary(name, r['fitness'], rmse_mm)

    print('\n' + '=' * 65)
    print('  KALMAN FILTER FITNESS (normalized space)')
    print('=' * 65)
    for model_name, filters in filter_results.items():
        print(f'\n  Model: {model_name}')
        for filt_name, res in filters.items():
            rmse_mm = res['rmse'] * L_range
            print_model_summary(f'  {filt_name}', res['fitness'], rmse_mm)

    print('\n' + '=' * 65)


def main(mat_file: str = 'CombinedPermutation_EXAMPLE_arrays.mat',
         permutation: int = 3):
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print('\n' + '=' * 65)
    print('  STEP 1: Data Loading')
    print('=' * 65)
    raw, norm, scale = load_and_prepare(mat_file, permutation=permutation)

    u_norm = norm['Pressure']
    y_norm = norm['Length']
    T      = norm['Time']
    N      = len(y_norm)

    print(f'  Samples : {N}  ({N * 0.01:.1f} s at 100 Hz)')
    print(f'  Pressure: [{scale["P_min"]:.1f}, {scale["P_max"]:.1f}] kPa')
    print(f'  Length  : [{scale["L_min"]:.2f}, {scale["L_max"]:.2f}] mm')

    # ------------------------------------------------------------------
    # 2. Fit NLARX models
    # ------------------------------------------------------------------
    print('\n' + '=' * 65)
    print('  STEP 2: NLARX Model Fitting')
    print('=' * 65)
    nlarx_results = fit_all_models(u_norm, y_norm, verbose=True)

    # ------------------------------------------------------------------
    # 3. Kalman filters
    # ------------------------------------------------------------------
    print('\n' + '=' * 65)
    print('  STEP 3: Kalman Filters (EKF / UKF / CKF)')
    print('=' * 65)
    filter_results = run_all_models_all_filters(
        nlarx_results, u_norm, y_norm, verbose=True
    )

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    _print_summary(nlarx_results, filter_results, scale)

    # ------------------------------------------------------------------
    # 5. Figures
    # ------------------------------------------------------------------
    plot_all(raw, norm, scale, nlarx_results, filter_results,
             permutation=permutation)

    t_elapsed = time.perf_counter() - t_start
    print(f'  Total elapsed: {t_elapsed:.1f} s\n')

    # ------------------------------------------------------------------
    # 6. Return everything for downstream use
    # ------------------------------------------------------------------
    return {
        'raw'           : raw,
        'norm'          : norm,
        'scale'         : scale,
        'nlarx_results' : nlarx_results,
        'filter_results': filter_results,
    }


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PAM Nonlinear SysID Pipeline — Unified Gimped Version')
    parser.add_argument('--mat',  default='CombinedPermutation_EXAMPLE_arrays.mat',
                        help='Path to .mat file')
    parser.add_argument('--perm', type=int, default=3,
                        help='Permutation index (1-based; file may have 1-8)')
    args = parser.parse_args()

    main(mat_file=args.mat, permutation=args.perm)
