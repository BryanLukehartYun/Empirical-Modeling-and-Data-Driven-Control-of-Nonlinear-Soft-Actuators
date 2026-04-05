% Note that the synthetic permutations loaded are NOT based on the
% original data used for the Technical Writeup, they are meant to
% demostrate that the code works
load('CombinedPermutation_EXAMPLE.mat')
Insert = Permutation3; 
% There exists 3 different permutations based on
%           - Permutation1
%           - Permutation2
%           - Permutation3
L = Insert.Length;  % Length - Output
P  = Insert.Pressure; % Pressure - Input

valid_idx = ~isnan(P) & ~isnan(L); %Make sure no NAN exists
P_v = P(valid_idx);
L_v = L(valid_idx);
T_v = Insert.Time(valid_idx);

Pressure = P_v;
Length = L_v;

u = Pressure; % Input (kPa)
y = Length;   % Output (mm)

% Min-Max Normalization (Vital for Nonlinear Solvers)
u_norm = (u - min(u)) / (max(u) - min(u));
y_norm = (y - min(y)) / (max(y) - min(y));

% 2. Create the iddata object (100 Hz = 0.01s Ts)
Ts = 0.01;
data = iddata(y_norm, u_norm, Ts);
data.InputName = 'Pressure';
data.OutputName = 'Length';

%% Implementation of the Sigmoid, Wavelet, and IdTreePartition

% Sigmoid Network
netSIG = idSigmoidNetwork('NumberOfUnits', 10);
orders = [2 2 1]; % Minimum Order to be able to track a Second Order System Response and Hysteresis
sys_nl_SIG = nlarx(data, orders, netSIG);

% Wavelet Network
opt = nlarxOptions;
opt.SearchOptions.MaxIterations = 20; 
opt.Display = 'on'; % Opted to take a look
opt.Focus = 'simulation';
net = idWaveletNetwork('NumberOfUnits', 10);
sys_nl_WAVE= nlarx(data, orders, net,opt);
% idTreePartition Network
netTree = idTreePartition('NumberOfUnits',10);
opt_tree = nlarxOptions;
opt_tree.SearchOptions.MaxIterations = 20;
opt_tree.Display = 'on';
opt_tree.Focus = 'prediction';
sys_nl_TREE = nlarx(data, orders, netTree, opt_tree);
% ---- Grabbing RMSE ----
[y_sim_SIG, fit_val_SIG] = compare(data, sys_nl_SIG);
fprintf('Sigmoid Final Model Fitness: %.2f%%\n', fit_val_SIG);

[y_sim_WAVE, fit_val_WAVE] = compare(data, sys_nl_WAVE);
fprintf('Wavelet Final Model Fitness: %.2f%%\n', fit_val_WAVE);

[y_sim_TREE, fit_val_TREE] = compare(data, sys_nl_TREE);
fprintf('TreePartition Final Model Fitness: %.2f%%\n', fit_val_TREE);

%% Prelude to Plotting

[y_sim_SIG, ~] = compare(data, sys_nl_SIG);

% Un-normalize: y_actual = y_norm * (max-min) + min
y_finalSIG = y_sim_SIG.OutputData * (max(L_v) - min(L_v)) + min(L_v);
y_measured = L_v; % Your original raw data

[y_sim_WAVE, ~] = compare(data, sys_nl_WAVE);
y_finalWAVE = y_sim_WAVE.OutputData * (max(L_v) - min(L_v)) + min(L_v);

[y_sim_TREE, ~] = compare(data,sys_nl_TREE);
y_finalTREE = y_sim_TREE.OutputData * (max(L_v) - min(L_v)) + min(L_v);
%%  Plotting Figures 1-3: Time Series vs NLARX | Hysteresis | Jacobian Proxy

usethislength = length(y_finalSIG);
figure(1)
subplot(3,1,1); 
plot(T_v(1:usethislength), y_measured(1:usethislength), 'b', T_v(1:usethislength), y_finalSIG(1:usethislength), 'r--');
legend('Measured (mm)', 'NLARX Estimate (mm)');
title(['Nonlinear State Estimation (Sigmoid):  ' num2str(fit_val_SIG) '% Fitness Match']);
grid on;

subplot(3,1,2); 
plot(T_v(1:usethislength), y_measured(1:usethislength), 'b', T_v(1:usethislength), y_finalWAVE(1:usethislength), 'r--');
legend('Measured (mm)', 'NLARX Estimate (mm)');
title(['Nonlinear State Estimation (Wavelet):  ' num2str(fit_val_WAVE) '% Fitness Match']);
grid on;

subplot(3,1,3); 
plot(T_v(1:usethislength), y_measured(1:usethislength), 'b', T_v(1:usethislength), y_finalTREE(1:usethislength), 'r--');
legend('Measured (mm)', 'NLARX Estimate (mm)');
title(['Nonlinear State Estimation (idTreePartition):  ' num2str(fit_val_TREE) '% Fitness Match']);
grid on;

%
u_measured = P_v;
figure(2);  hold on;
plot(u_measured(1:usethislength), y_measured(1:usethislength),'-k','LineWidth',2)
plot(u_measured(1:usethislength), y_finalSIG(1:usethislength),'-r','LineWidth',2)
plot(u_measured(1:usethislength), y_finalWAVE(1:usethislength),'--g','LineWidth',2)
plot(u_measured(1:usethislength), y_finalTREE(1:usethislength),'--b','LineWidth',2)
title('Comparison of Pressure-Length Hysteresis between Measured and NLARX Models')
legend('Measured Hysteresis','Simulated Hysteresis - Sigmoid', 'Simulated Hysteresis - Wavelet','Simulated Hysteresis - idTreePartition')
%
figure(3); hold on;
dy = diff(y_finalSIG) ./ diff(data.SamplingInstants); 
plot(data.SamplingInstants(1:end-1), dy,'r-');

dy = diff(y_finalWAVE) ./ diff(data.SamplingInstants); 
plot(data.SamplingInstants(1:end-1), dy,'b--');

dy = diff(y_finalTREE) ./ diff(data.SamplingInstants); 
plot(data.SamplingInstants(1:end-1), dy,'g-.');
legend('Gradient of Sigmoid','Gradient of Wavelet','Gradient of idTreePartition')
title('Gradient (Jacobian Proxy) of NLARX functions');
%% Kalman Filter - Initialization of values and setup

nonlin_SIG = sys_nl_SIG.Nonlinearity;
nonlin_WAVE = sys_nl_WAVE.Nonlinearity;
nonlin_TREE = sys_nl_TREE.Nonlinearity;
MeasurementNoise = 5e-3;
ProcessNoise = diag([1e-6, 1e-6, 1e-5]);

f = @(x, u_new) nlarx_state_transition(x, u_new, nonlin_SIG); % THE MAN
f1 = @(xWa, u_newWa) nlarx_state_transition(xWa, u_newWa, nonlin_WAVE); %THE MYTH
f2 = @(xT, u_newT) nlarx_state_transition(xT, u_newT, nonlin_TREE); % THE LEGEND
offset = 0;
h = @(x) x(1) + offset;
hWa = @(xWa) xWa(1) + offset;
h_oT = @(xT) xT(1) + offset;

initialState = [y_norm(1); y_norm(1); u_norm(1)];
%  EKF
obj_ekf = extendedKalmanFilter(f, h, initialState);
obj_ekfWa = extendedKalmanFilter(f1,hWa,initialState);
obj_ekfTree = extendedKalmanFilter(f2,h_oT,initialState);
obj_ekf.ProcessNoise = ProcessNoise
obj_ekf.MeasurementNoise = MeasurementNoise;
obj_ekfWa.ProcessNoise =ProcessNoise
obj_ekfWa.MeasurementNoise = MeasurementNoise;
obj_ekfTree.ProcessNoise = ProcessNoise
obj_ekfTree.MeasurementNoise = MeasurementNoise;
% UKF
obj_ukf = unscentedKalmanFilter(f, h, initialState);
obj_ukf.ProcessNoise = MeasurementNoise;
obj_ukf.MeasurementNoise = MeasurementNoise;

obj_ukfWa = unscentedKalmanFilter(f1, hWa, initialState);
obj_ukfWa.ProcessNoise = MeasurementNoise;
obj_ukfWa.MeasurementNoise = MeasurementNoise;  

obj_ukfTree = unscentedKalmanFilter(f2,h_oT,initialState);
obj_ukfTree.MeasurementNoise = MeasurementNoise;
obj_ukfTree.ProcessNoise =ProcessNoise

%% RUN THE LOOP
tic;
N = length(y_norm);

% Preallocation of the Estimate
y_est_ekf = zeros(N, 1);       
y_est_ukf = zeros(N, 1); 

y_est_ekfWa = zeros(N,1);
y_est_ukfWa = zeros(N, 1); 

y_est_ekfTree = zeros(N,1);
y_est_ukfTree = zeros(N,1);

fprintf('Running EKF and UKF simultaneously on %d samples...\n', N);

k = 1; % Initializing the k increment counter
while k <= N
    % --- EKF UPDATE ---
    x_corr_e = correct(obj_ekf, y_norm(k));
    y_est_ekf(k) = x_corr_e(1);
    predict(obj_ekf, u_norm(k));
    
    x_corr_e_Wa = correct(obj_ekfWa, y_norm(k));
    y_est_ekfWa(k) = x_corr_e_Wa(1);
    predict(obj_ekfWa, u_norm(k));

    x_corr_e_T = correct(obj_ekfTree, y_norm(k));
    y_est_ekfTree(k) = x_corr_e_T(1);
    predict(obj_ekfTree, u_norm(k));
    % --- UKF UPDATE ---
    x_corr_u = correct(obj_ukf, y_norm(k));
    y_est_ukf(k) = x_corr_u(1);
    predict(obj_ukf, u_norm(k));
    
    x_corr_uWa = correct(obj_ukfWa, y_norm(k));
    y_est_ukfWa(k) = x_corr_uWa(1);
    predict(obj_ukfWa, u_norm(k));

    x_corr_uTREE = correct(obj_ukfTree, y_norm(k));
    y_est_ukfTree(k) = x_corr_uTREE(1);
    predict(obj_ukfTree, u_norm(k));
    
    k = k + 1;
    if mod(k, 100) == 0 % Lets me know where Loop stands
    fprintf('Iteration: %d\n', k);
    end
end

toc;
%% Plot the Kalman Filter Response
% Returning Estimate to original scale 
y_ekf_mm = y_est_ekf * (max(L_v) - min(L_v)) + min(L_v);
y_ukf_mm = y_est_ukf * (max(L_v) - min(L_v)) + min(L_v);
y_ekf_mmWa = y_est_ekfWa * (max(L_v) - min(L_v)) + min(L_v);
y_ukf_mmWa = y_est_ukfWa * (max(L_v) - min(L_v)) + min(L_v);
y_ekf_mmTREE = y_est_ekfTree * (max(L_v) - min(L_v)) + min(L_v);
y_ukf_mmTREE = y_est_ukfTree * (max(L_v) - min(L_v)) + min(L_v);

y_raw_mm = L_v; 

figure(4);
tiledlayout(3,1);
nexttile;
plot(T_v(1:N), y_raw_mm(1:N), 'Color', 'Black', 'LineWidth', 2); hold on;
plot(T_v(1:N), y_ekf_mm, 'b-', 'LineWidth', 1.5);
plot(T_v(1:N), y_ukf_mm, 'r-.', 'LineWidth', 1.5); % UKF is Red Dashed
legend('Raw Data', 'EKF Estimate', 'UKF Estimate');
title('Estimator Comparison - Sigmoid: EKF vs UKF');
xlabel('Time (s)');
ylabel('Length (mm)');
xlim([0,100])
grid on;

nexttile;
plot(T_v(1:N), y_raw_mm(1:N), 'Color', 'Black', 'LineWidth', 2); hold on;
plot(T_v(1:N), y_ekf_mmWa, 'b-', 'LineWidth', 1.5);
plot(T_v(1:N), y_ukf_mmWa, 'r-.', 'LineWidth', 1.5); % UKF is Red Dashed
legend('Raw Data', 'EKF Estimate', 'UKF Estimate');
title('Estimator Comparison - Wavelet NLARX: EKF vs UKF');
xlabel('Time (s)');
ylabel('Length (mm)');
xlim([0,100])
grid on;

nexttile;
plot(T_v(1:N), y_raw_mm(1:N), 'Color', 'Black', 'LineWidth', 2); hold on;
plot(T_v(1:N), y_ekf_mmTREE, 'b-', 'LineWidth', 1.5);
plot(T_v(1:N), y_ukf_mmTREE, 'r-.', 'LineWidth', 1.5); % UKF is Red Dashed
legend('Raw Data', 'EKF Estimate', 'UKF Estimate');
title('Estimator Comparison - idTreePart NLARX: EKF vs UKF');
xlabel('Time (s)');
ylabel('Length (mm)');
xlim([0,100])
grid on;
%% Hysteresis Comparison (Pressure vs Displacement) 
figure(5); 
tiledlayout(3,1)
nexttile; hold on;
plot(u_measured(1:usethislength), y_measured(1:usethislength),'-k','LineWidth',2)
plot(u_measured(1:usethislength), y_finalSIG(1:usethislength),'-r','LineWidth',2)
plot(u_measured(1:usethislength), y_ekf_mm(1:usethislength),'-.b','LineWidth',2)
plot(u_measured(1:usethislength), y_ukf_mm(1:usethislength),'-.g','LineWidth',2)
legend('Measured Hysteresis','Simulated Hysteresis - Sigmoid', 'Simulated Hysteresis - UKF','Simulated Hysteresis - EKF')
title('Pressure-Length Comparison of Hysteresis across Measured, NLARX (Sigmoid Function), and Kalman Filter')

nexttile; hold on
plot(u_measured(1:usethislength), y_measured(1:usethislength),'-k','LineWidth',2)
plot(u_measured(1:usethislength), y_finalWAVE(1:usethislength),'-m','LineWidth',2)
plot(u_measured(1:usethislength), y_ekf_mmWa(1:usethislength),'-.b','LineWidth',2)
plot(u_measured(1:usethislength), y_ukf_mmWa(1:usethislength),'-.g','LineWidth',2)
legend('Measured Hysteresis','Simulated Hysteresis - Wavelet', 'Simulated Hysteresis - UKF','Simulated Hysteresis - EKF')
title('Pressure-Length Comparison of Hysteresis across Measured, NLARX (Wavelet Function), and Kalman Filter')

nexttile; hold on
plot(u_measured(1:usethislength), y_measured(1:usethislength),'-k','LineWidth',2)
plot(u_measured(1:usethislength), y_finalTREE(1:usethislength),'-m','LineWidth',2)
plot(u_measured(1:usethislength), y_ekf_mmTREE(1:usethislength),'-.b','LineWidth',2)
plot(u_measured(1:usethislength), y_ukf_mmTREE(1:usethislength),'-.g','LineWidth',2)
legend('Measured Hysteresis','Simulated Hysteresis - Wavelet', 'Simulated Hysteresis - UKF','Simulated Hysteresis - EKF')
title('Pressure-Length Comparison of Hysteresis across Measured, NLARX (idTreePart Function), and Kalman Filter')

%% Helper Function
% 
% ---------------------------------------------------------
% HELPER FUNCTION FOR running NLARX State Transition based on 2nd Order
% ---------------------------------------------------------
function x_next = nlarx_state_transition(x, u_new, net)
    y_k = x(1);
    y_prev = x(2);
    u_prev = x(3);

    regressors = [y_k, y_prev, u_new, u_prev];
    
    y_next = evaluate(net, regressors);
    x_next = [y_next; y_k; u_new];
end