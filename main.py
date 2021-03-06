import os
used_gpu = '2,3'
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = used_gpu

import argparse
from utils import *
from resnet import *
from Trainer import *
from torch.optim import *
from data_transform import *
from se_inception_v3 import *
from torch.utils.data.sampler import RandomSampler, SequentialSampler


def create_config():
    parser = argparse.ArgumentParser(description='Parameters for Cdiscount Classification')

    # Data Settings
    parser.add_argument('--train_bson_path', type=str, default='/data/lixiang/train.bson', help='where original training data')
    parser.add_argument('--num_classes', type=int, default=5270, help='how many classes to be classified')
    parser.add_argument('--num_train', type=int, default=12371293, help='how many training datas')
    parser.add_argument('--data_worker', type=int, default=5, help='how many workers to read datas')

    # Model Settings
    parser.add_argument('--batch_size', type=int, default=128, help='how many samples in a batch')
    parser.add_argument('--image_size', type=tuple, default=(3, 224, 224), help='image size as (C, H, W)')
    parser.add_argument('--saved_model', type=str, default="resnet50-ep-4acc0.4157-model.pth",
                        help='the name of saved model')
    parser.add_argument('--optimizer_path', type=str, default="resnet50-ep-4-opt.pth", help='the path of saved optimizer')

    # Optimizer Settings
    parser.add_argument('--optimizer', type=str, default='SGD', help='which optimizer to apply')
    parser.add_argument('--initial_learning_rate', type=float, default=0.05, help='initial learning rate')
    parser.add_argument('--momentum', type=float, default=0.9, help='momentum')
    parser.add_argument('--weight_decay', type=float, default=0.0001, help='weight decay')
    return parser.parse_args().__dict__


# total = 7069896
a = "LB=0.69673_se-inc3_00026000_model.pth"
b = "inception_v3_google-1a9a5a14.pth"
c = "ep-14acc0.6891-model.pth"
co = "ep-14-opt.pth"
cuda = torch.cuda.is_available()
total = 12371293
np.random.seed(2333)
to = np.arange(total)
to = np.random.permutation(to)
val_mask = to[:int(total*0.1)]
train_mask = to[int(total*0.1):]
print("finish mask")


def run(cfg):
    # net = SEInception3(num_classes=cfg["num_classes"])
    net = ResNet50(num_classes=cfg["num_classes"])
    print("use gpu:", used_gpu)
    print("use model:", net.name)
    if cfg["saved_model"]:
        print("*-------Begin Loading Saved Models!------*")
        net.load_pretrained_model('saved_models/' + cfg["saved_model"], skip=["fc.weight", "fc.bias"])

    if len(used_gpu) > 1 and cuda:
        distri = True
        net = torch.nn.DataParallel(net)
    else:
        distri = False
    print("loaded model:", 'saved_models/' + cfg["saved_model"])
    print("whether distributed:", distri)

    if cfg['optimizer'] == 'SGD':
        optimizer = SGD(filter(lambda p: p.requires_grad, net.parameters()),
                        lr=cfg['initial_learning_rate'], momentum=cfg['momentum'],
                        weight_decay=cfg['weight_decay'])
    elif cfg['optimizer'] == 'Adam':
        optimizer = Adam(filter(lambda p: p.requires_grad, net.parameters()),
                         lr=cfg['initial_learning_rate'],
                         weight_decay=cfg['weight_decay'])

    if cfg["optimizer_path"]:
        print("*-----Begin Loading Saved optimizer!-----*")
        load_optimizer(optimizer, 'saved_models/' + cfg['optimizer_path'])

    loss = F.cross_entropy
    trainer = Trainer(net, optimizer, loss, cfg['batch_size'], distri)
    lr_step = MultiStepLR(optimizer, [2, 4, 6], gamma=0.5)
    # lr_step = ReduceLROnPlateau(optimizer, 'min', patience=3)

    print("*----------Begin Loading Data!-----------*")
    data_frame = extract_categories_df(cfg['train_bson_path'])
    train_dataset = CdiscountTrain(cfg['train_bson_path'], data_frame, train_mask,
                                   transform=train_augment)
    train_loader = DataLoader(train_dataset,
                              sampler=RandomSampler(train_dataset),
                              batch_size=cfg['batch_size'],
                              drop_last=True,
                              num_workers=cfg['data_worker'])

    valid_dataset = CdiscountVal(cfg['train_bson_path'], data_frame, val_mask,
                                 transform=valid_augment)
    valid_loader = DataLoader(valid_dataset,
                              sampler=SequentialSampler(valid_dataset),
                              batch_size=cfg['batch_size'],
                              drop_last=False,
                              num_workers=cfg['data_worker'])

    print("*------------Begin Training!-------------*")
    trainer.loop(train_loader, valid_loader, lr_step)


if __name__ == "__main__":
    cfg =create_config()
    run(cfg)
