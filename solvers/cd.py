import numpy as np
from scipy import sparse

from benchopt import BaseSolver
from benchopt import safe_import_context

with safe_import_context() as import_ctx:
    from numba import njit

if import_ctx.failed_import:

    def njit(f):  # noqa: F811
        return f


@njit
def st(x, mu):
    if x > mu:
        return x - mu
    if x < - mu:
        return x + mu
    return 0


@njit
def prox_mcp(x, lmbd, gamma):
    if x > gamma * lmbd:
        return x
    if x < - gamma * lmbd:
        return x
    return gamma / (gamma - 1) * st(x, lmbd)


class Solver(BaseSolver):
    name = "cd"
    install_cmd = 'conda'
    requirements = ['numba']

    def set_objective(self, X, y, lmbd, gamma):
        # use Fortran order to compute gradient on contiguous columns
        self.X, self.y = np.asfortranarray(X), y
        self.lmbd, self.gamma = lmbd, gamma

        # Make sure we cache the numba compilation.
        self.run(1)

    def run(self, n_iter):
        if sparse.issparse(self.X):
            self.w = self.sparse_cd(
                self.X.data, self.X.indices, self.X.indptr, self.y, self.lmbd,
                self.gamma, n_iter)
        else:
            self.w = self.cd(self.X, self.y, self.lmbd, self.gamma, n_iter)

    @staticmethod
    @njit
    def cd(X, y, lmbd, gamma, n_iter):
        n_features = X.shape[1]
        R = np.copy(y)
        w = np.zeros(n_features)
        for _ in range(n_iter):
            for j in range(n_features):
                old = w[j]
                w[j] = prox_mcp(w[j] + X[:, j] @ R, lmbd, gamma)
                diff = old - w[j]
                if diff != 0:
                    R += diff * X[:, j]
        return w

    @staticmethod
    @njit
    def sparse_cd(X_data, X_indices, X_indptr, y, lmbd, gamma, n_iter):
        n_features = len(X_indptr) - 1
        w = np.zeros(n_features)
        R = np.copy(y)
        for _ in range(n_iter):
            for j in range(n_features):
                old = w[j]
                start, end = X_indptr[j:j+2]
                scal = 0.
                for ind in range(start, end):
                    scal += X_data[ind] * R[X_indices[ind]]
                w[j] = prox_mcp(w[j] + scal, lmbd, gamma)
                diff = old - w[j]
                if diff != 0:
                    for ind in range(start, end):
                        R[X_indices[ind]] += diff * X_data[ind]
        return w

    def get_result(self):
        return self.w
