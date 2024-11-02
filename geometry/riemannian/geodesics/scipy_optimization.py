#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 24 11:48:55 2024

@author: fmry
"""

#%% Sources

#%% Modules

from geometry.setup import *

from geometry.riemannian.manifolds import RiemannianManifold
from geometry.stochastic.manifolds import IndicatorManifold

#%% Gradient Descent Estimation of Geodesics

class ScipyOptimization(ABC):
    def __init__(self,
                 M:RiemannianManifold,
                 batch_size:int=None,
                 init_fun:Callable[[Array, Array, int], Array]=None,
                 T:int=100,
                 tol:float=1e-4,
                 max_iter:int=1000,
                 method:str='BFGS',
                 seed:int=2712,
                 )->None:
        
        if method not in['CG', 'BFGS', 'dogleg', 'trust-ncg', 'trust-exact']:
            raise ValueError(f"Method, {method}, should be gradient based. Choose either: \n CG, BFGS, dogleg, trust-ncg, trust-exact")
            
        if init_fun is None:
            self.init_fun = lambda z0, zT, T: (zT-z0)*jnp.linspace(0.0,
                                                                   1.0,
                                                                   T,
                                                                   endpoint=False,
                                                                   dtype=z0.dtype)[1:].reshape(-1,1)+z0
        else:
            self.init_fun = init_fun
            
        if batch_size is None:
            self.batch_size = M.emb_dim
        else:
            self.batch_size = batch_size
            
        self.M = M
        self.T = T
        self.method = method
        self.tol = tol
        self.max_iter = max_iter
        self.seed = seed
        
        self.save_zt = []
        
        self.z0 = None
        self.zT = None
        
        return
    
    def __str__(self)->str:
        
        return "Geodesic Computation Object using Scipy Optimizers"
    
    def energy(self, 
               zt:Array,
               *args,
               )->Array:
        
        zt = zt.reshape(-1, self.M.dim)
        
        batch = self.PM.idx_set()
        SG0 = self.PM.SG(self.z0, batch)
        SG = vmap(self.PM.SG, in_axes=(0,None))(zt, batch)
        
        term1 = zt[0]-self.z0
        val1 = jnp.einsum('i,ij,j->', term1, SG0, term1)
        
        term2 = zt[1:]-zt[:-1]
        val2 = jnp.einsum('ti,tij,tj->t', term2, SG[:-1], term2)
        
        term3 = self.zT-zt[-1]
        val3 = jnp.einsum('i,ij,j->', term3, SG[-1], term3)
        
        return val1+jnp.sum(val2)+val3
    
    def Denergy(self,
                zt:Array,
                )->Array:
        
        return grad(self.energy)(zt)
    
    def HessEnergy(self,
                   zt:Array,
                   )->Array:
        
        return hessian(self.energy)(zt)
    
    def HessPEnergy(self,
                   zt:Array,
                   p:Array,
                   )->Array:
        
        return jnp.dot(hessian(self.energy)(zt), p)
    
    def callback(self,
                 zt:Array
                 )->Array:
        
        self.save_zt.append(zt.reshape(-1, self.dim))
        
        return
    
    def __call__(self, 
                 z0:Array,
                 zT:Array,
                 step:str="while",
                 )->Array:
        
        self.PM = IndicatorManifold(self.M, self.batch_size, self.seed)
        
        self.z0 = z0
        self.zT = zT
        
        self.dim = len(z0)
        zt = self.init_fun(z0,zT,self.T)
        
        if step == "while":
            res = minimize(fun = self.energy, 
                           x0=zt.reshape(-1), 
                           method=self.method, 
                           jac=self.Denergy,
                           hess=self.HessEnergy,
                           hessp=self.HessPEnergy,
                           tol=self.tol,
                           options={'maxiter': self.max_iter}
                           )
        
            zt = res.x.reshape(-1,self.dim)
            zt = jnp.vstack((z0, zt, zT))
            grad =  res.jac.reshape(-1,self.dim)
            idx = res.nit
        elif step == "for":
            res = minimize(fun = self.energy,
                           x0=zt.reshape(-1),
                           method=self.method,
                           jac=self.Denergy,
                           hess=self.HessEnergy,
                           hessp=self.HessPEnergy,
                           callback=self.callback,
                           tol=self.tol,
                           options={'maxiter': self.max_iter}
                           )
            
            zt = jnp.stack([zt.reshape(-1,self.dim) for zt in self.save_zt])
            
            grad = vmap(self.Denergy)(zt)
            zt = vmap(lambda z: jnp.vstack((z0, z, zT)))(zt)
            idx = self.max_iter
        else:
            raise ValueError(f"step argument should be either for or while. Passed argument is {step}")
        
        return zt, grad, idx
    
    
    