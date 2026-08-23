"""
Spacecraft Rotational Dynamics Model & Discretization Engine
PCC Substrate: Rigid Body Attitude Dynamics
"""

import numpy as np

class SpacecraftDynamics:
    def __init__(self, inertia_matrix=None):
        if inertia_matrix is None:
            # Default CubeSat / SmallSat moment of inertia (kg * m^2)
            self.I = np.diag([0.10, 0.12, 0.08])
        else:
            self.I = np.array(inertia_matrix, dtype=np.float64)
        self.I_inv = np.linalg.inv(self.I)

    def discrete_step_matrices(self, dt=0.1):
        """
        Linearized discrete-time transition matrices A and B
        for state x = [omega_x, omega_y, omega_z]^T
        and input u = [torque_x, torque_y, torque_z]^T (RCS pulse)
        
        x_{k+1} = A * x_k + B * u_k
        """
        # Linearized around small angular rates (A ~ Identity)
        A = np.eye(3, dtype=np.float64)
        B = dt * self.I_inv
        return A, B

    def predict_state(self, x0, u, dt=0.1):
        """
        Predict post-maneuver state given initial state x0 and torque input u
        """
        A, B = self.discrete_step_matrices(dt)
        return A @ np.array(x0, dtype=np.float64) + B @ np.array(u, dtype=np.float64)

if __name__ == "__main__":
    sat = SpacecraftDynamics()
    A, B = sat.discrete_step_matrices(0.1)
    print("State Transition Matrix A:\n", A)
    print("Input Matrix B:\n", B)
