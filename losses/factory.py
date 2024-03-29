import torch
import torch.nn as nn
import torch.nn.functional as F


class LabelSmoothingLoss(nn.Module):

    def __init__(self, classes, smoothing=0.0, dim=-1, log_softmax=True):
        super(LabelSmoothingLoss, self).__init__()
        self.confidence = 1.0 - smoothing
        self.smoothing = smoothing
        self.cls = classes
        self.dim = dim
        self.log_softmax = log_softmax

    def forward(self, pred, target):
        """Taylor Softmax and log are already applied on the logits"""
        if self.log_softmax: pred = pred.log_softmax(dim=self.dim)
        with torch.no_grad():
            true_dist = torch.zeros_like(pred)
            true_dist.fill_(self.smoothing / (self.cls - 1))
            true_dist.scatter_(1, target.data.unsqueeze(1), self.confidence)
        return torch.mean(torch.sum(-true_dist * pred, dim=self.dim))


class LabelSmoothingOneHot(nn.Module):
    def __init__(self, smoothing=0.1, average='mean', log_softmax=True):
        super(LabelSmoothingOneHot, self).__init__()
        self.confidence = 1.0 - smoothing
        self.smoothing = smoothing
        self.average = average
        self.log_softmax = log_softmax

    def forward(self, x, target):
        x = x.float()
        target = target.float()
        if self.log_softmax: x = x.log_softmax(dim=-1)
        nll_loss = -x * target
        nll_loss = nll_loss.sum(-1)
        smooth_loss = -x.mean(dim=-1)
        loss = self.confidence * nll_loss + self.smoothing * smooth_loss
        if self.average == 'mean':
            return loss.mean()
        else:
            return loss


class NoiseLabelSmoothingOneHot(nn.Module):
    def __init__(self, smoothing=0.1, average='mean', log_softmax=True):
        super(NoiseLabelSmoothingOneHot, self).__init__()
        self.confidence = 1.0 - smoothing
        self.smoothing = smoothing
        self.average = average
        self.log_softmax = log_softmax

    def forward(self, x, target):
        x = x.float()
        target = target.float()
        weights, _ = target.max(dim=1)
        if self.log_softmax: x = x.log_softmax(dim=-1)
        nll_loss = -x * target
        nll_loss = nll_loss.sum(-1)
        smooth_loss = -x.mean(dim=-1)
        loss = self.confidence * nll_loss + self.smoothing * smooth_loss
        loss = weights * loss
        if self.average == 'mean':
            return loss.mean()
        else:
            return loss


class CrossEntropyOneHot(nn.Module):
    def __init__(self):
        super(CrossEntropyOneHot, self).__init__()

    def forward(self, x, target):
        labels = target.argmax(dim=1)
        return nn.CrossEntropyLoss()(x, labels)


class NoiseCrossEntropyOneHot(nn.Module):
    def __init__(self):
        super(NoiseCrossEntropyOneHot, self).__init__()

    def forward(self, x, target):
        weights, labels = target.max(dim=1)
        loss = nn.CrossEntropyLoss(reduction='none')(x, labels)
        loss = (weights * loss).mean()
        return loss


class F1_Loss(nn.Module):
    '''Calculate F1 score. Can work with gpu tensors
    The original implmentation is written by Michal Haltuf on Kaggle.
    Returns
    -------
    torch.Tensor
        `ndim` == 1. epsilon <= val <= 1
    Reference
    ---------
    - https://www.kaggle.com/rejpalcz/best-loss-function-for-f1-score-metric
    - https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html#sklearn.metrics.f1_score
    - https://discuss.pytorch.org/t/calculating-precision-recall-and-f1-score-in-case-of-multi-label-classification/28265/6
    - http://www.ryanzhang.info/python/writing-your-own-loss-function-module-for-pytorch/
    '''

    def __init__(self, epsilon=1e-7):
        super().__init__()
        self.epsilon = epsilon

    def forward(self, y_pred, y_true, ):
        assert y_pred.ndim == 2
        assert y_true.ndim == 2

        tp = (y_true * y_pred).sum(dim=0).to(torch.float32)
        tn = ((1 - y_true) * (1 - y_pred)).sum(dim=0).to(torch.float32)
        fp = ((1 - y_true) * y_pred).sum(dim=0).to(torch.float32)
        fn = (y_true * (1 - y_pred)).sum(dim=0).to(torch.float32)

        precision = tp / (tp + fp + self.epsilon)
        recall = tp / (tp + fn + self.epsilon)

        f1 = 2 * (precision * recall) / (precision + recall + self.epsilon)
        f1 = f1.clamp(min=self.epsilon, max=1 - self.epsilon)
        return 1 - f1.mean()


# https://github.com/Newbeeer/L_DMI/blob/master/fashion/main.py
def DMI_loss(output, target, num_classes):
    outputs = F.softmax(output, dim=1)
    targets = target.reshape(target.size(0), 1).cpu()
    y_onehot = torch.FloatTensor(target.size(0), num_classes).zero_()
    y_onehot.scatter_(1, targets, 1)
    y_onehot = y_onehot.transpose(0, 1).cuda()
    mat = y_onehot @ outputs
    mat = mat / target.size(0)
    return -1.0 * torch.log(torch.abs(torch.det(mat.float())) + 0.001)