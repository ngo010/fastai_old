
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################
        # file to edit: /data1/jhoward/git/fastai_v1/dev_nb/001b_fit.ipynb

import pickle, gzip, torch, math, numpy as np, torch.nn.functional as F
from pathlib import Path
from IPython.core.debugger import set_trace
from torch import nn, optim, tensor

from torch.utils.data import TensorDataset, Dataset, DataLoader
from dataclasses import dataclass
from typing import Any, Collection, Callable
from functools import partial, reduce
from numbers import Number

def is_listy(x)->bool: return isinstance(x, (tuple,list))

def loss_batch(model, xb, yb, loss_fn, opt=None):
    if not is_listy(xb): xb = [xb]
    if not is_listy(yb): yb = [yb]
    loss = loss_fn(model(*xb), *yb)

    if opt is not None:
        loss.backward()
        opt.step()
        opt.zero_grad()

    return loss.item(), len(yb)

def fit(epochs, model, loss_fn, opt, train_dl, valid_dl):
    for epoch in range(epochs):
        model.train()
        for xb,yb in train_dl: loss,_ = loss_batch(model, xb, yb, loss_fn, opt)

        model.eval()
        with torch.no_grad():
            losses,nums = zip(*[loss_batch(model, xb, yb, loss_fn)
                                for xb,yb in valid_dl])
        val_loss = np.sum(np.multiply(losses,nums)) / np.sum(nums)

        print(epoch, val_loss)

class Lambda(nn.Module):
    def __init__(self, func):
        super().__init__()
        self.func=func

    def forward(self, x): return self.func(x)

def ResizeBatch(*size): return Lambda(lambda x: x.view((-1,)+size))
def Flatten(): return Lambda(lambda x: x.view((x.size(0), -1)))
def PoolFlatten(): return nn.Sequential(nn.AdaptiveAvgPool2d(1), Flatten())

def conv2d(ni, nf, ks=3, stride=1, padding=None):
    if padding is None and stride==1: padding = ks//2
    return nn.Conv2d(ni, nf, kernel_size=ks, stride=stride, padding=padding)

def conv2d_relu(ni, nf, ks=3, stride=1, padding=None, bn=False):
    layers = [conv2d(ni, nf, ks=ks, stride=stride, padding=padding), nn.ReLU()]
    if bn: layers.append(nn.BatchNorm2d(nf))
    return nn.Sequential(*layers)

def conv2d_trans(ni, nf, ks=2, stride=2, padding=0):
    return nn.ConvTranspose2d(ni, nf, kernel_size=ks, stride=stride, padding=padding)

@dataclass
class DatasetTfm(Dataset):
    ds: Dataset
    tfm: Callable = None

    def __len__(self): return len(self.ds)

    def __getitem__(self,idx):
        x,y = self.ds[idx]
        if self.tfm is not None: x = self.tfm(x)
        return x,y

def conv2_relu(nif, nof, ks, stride):
    return nn.Sequential(nn.Conv2d(nif, nof, ks, stride, padding=ks//2), nn.ReLU())

def simple_cnn(actns, kernel_szs, strides):
    layers = [conv2_relu(actns[i], actns[i+1], kernel_szs[i], stride=strides[i])
        for i in range(len(strides))]
    layers.append(PoolFlatten())
    return nn.Sequential(*layers)

def ifnone(a,b):
    "`a` if its not None, otherwise `b`"
    return b if a is None else a

default_device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

def to_device(b, device):
    device = ifnone(device, default_device)
    if is_listy(b): return [to_device(o, device) for o in b]
    return b.to(device)

@dataclass
class DeviceDataLoader():
    dl: DataLoader
    device: torch.device

    def __len__(self): return len(self.dl)
    def proc_batch(self,b): return to_device(b, self.device)

    def __iter__(self):
        self.gen = map(self.proc_batch, self.dl)
        return iter(self.gen)

    @classmethod
    def create(cls, *args, device=default_device, **kwargs): return cls(DataLoader(*args, **kwargs), device=device)

def fit(epochs, model, loss_fn, opt, train_dl, valid_dl):
    for epoch in range(epochs):
        model.train()
        for xb,yb in train_dl: loss,_ = loss_batch(model, xb, yb, loss_fn, opt)

        model.eval()
        with torch.no_grad():
            losses,nums = zip(*[loss_batch(model, xb, yb, loss_fn)
                                for xb,yb in valid_dl])
        val_loss = np.sum(np.multiply(losses,nums)) / np.sum(nums)

        print(epoch, val_loss)

@dataclass
class DataBunch():
    train_dl:DataLoader
    valid_dl:DataLoader
    device:torch.device=None

    @classmethod
    def create(cls, train_ds, valid_ds, bs=64, train_tfm=None, valid_tfm=None, device=None, **kwargs):
        return cls(DeviceDataLoader.create(DatasetTfm(train_ds, train_tfm), bs,   shuffle=True,  device=device, **kwargs),
                   DeviceDataLoader.create(DatasetTfm(valid_ds, valid_tfm), bs*2, shuffle=False, device=device, **kwargs),
                   device=device)

class Learner():
    def __init__(self, data, model):
        self.data,self.model = data,to_device(model, data.device)

    def fit(self, epochs, lr, opt_fn=optim.SGD):
        opt = opt_fn(self.model.parameters(), lr=lr)
        loss_fn = F.cross_entropy
        fit(epochs, self.model, loss_fn, opt, self.data.train_dl, self.data.valid_dl)