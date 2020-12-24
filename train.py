import numpy as np
import torch
from dataset import get_dataloader
from shared_funcs import read_csv, write_to_csv
from torch import nn, optim
from torchvision import models


def evaluate_model(model, dl, loss_func, device):
    model.eval()
    with torch.no_grad():
        losses = []
        total_count = 0
        total_correct = 0

        for X, y in dl:
            X, y = X.to(device), y.to(device)

            logits = model(X)
            loss = loss_func(logits, y)
            losses.append(loss.item())

            pred = logits.argmax(1)
            total_correct += (pred == y).sum().item()
            total_count += y.size(0)

    return total_correct / total_count, np.mean(losses)


def train_model(model, dl, loss_func, optimizer, device):
    model.train()
    train_loss = []
    total_count = 0
    total_correct = 0
    for X, y in dl:
        model.zero_grad()
        X, y = X.to(device), y.to(device)

        logits = model(X)
        loss = loss_func(logits, y)
        train_loss.append(loss.item())

        pred = logits.argmax(1)
        total_correct += (pred == y).sum().item()
        total_count += y.size(0)

        loss.backward()
        optimizer.step()

    return total_correct / total_count, np.mean(train_loss)


def train_validate_test(
        epochs, model, optimizer, scheduler, loss_func,
        train_dl, val_dl, test_dl, device):
    train_loss = []
    train_acc = []
    val_loss = []
    val_acc = []
    best_val_acc = -1
    best_weights = None
    for epoch in range(epochs):
        # Train
        acc, loss = train_model(model, train_dl, loss_func, optimizer, device)
        train_loss.append(loss)
        train_acc.append(acc)
        scheduler.step()

        # Validate
        acc, loss = evaluate_model(model, val_dl, loss_func, device)
        val_acc.append(acc)
        val_loss.append(loss)

        print("Epoch: {}".format(epoch + 1))
        print("Validation acc: {}, Validation loss: {}\n"
              .format(acc, loss))

        # Save model if improved
        if not best_weights or val_acc[-1] > best_val_acc:
            best_weights = model.state_dict()
            best_val_acc = val_acc[-1]

    # Test
    model.load_state_dict(best_weights)
    test_acc, test_loss = evaluate_model(model, test_dl, loss_func, device)
    print("Test acc: {}, Test loss: {}".format(test_acc, test_loss))
    return best_weights, train_loss, train_acc, val_loss, val_acc, test_loss, test_acc


if __name__ == '__main__':
    # Set hyperparameters
    lr = 0.001
    betas = (0.9, 0.999)
    eps = 1e-8
    weight_decay = 0
    epochs = 25
    step_size = 5
    gamma = 0.1
    batch_size = 32
    img_size = 256
    crop_size = 224  # smallest is 224
    dropout = 0.2
    use_gpu = False
    use_data_augmentation = True
    num_classes = 3
    image_dir = './data/images'
    path_to_save_model = './models/model.pth'

    # Read data
    X_train = read_csv('X_train.csv')
    y_train = read_csv('y_train.csv')
    X_val = read_csv('X_val.csv')
    y_val = read_csv('y_val.csv')
    X_test = read_csv('X_test.csv')
    y_test = read_csv('y_test.csv')
    train_dl = get_dataloader(
        X_train, y_train, batch_size, image_dir, img_size, crop_size, use_data_augmentation
    )
    val_dl = get_dataloader(
        X_val, y_val, batch_size, image_dir, img_size, crop_size, False
    )
    test_dl = get_dataloader(
        X_test, y_test, batch_size, image_dir, img_size, crop_size, False
    )

    # Build model
    mobilenet = models.mobilenet_v2(pretrained=True)
    mobilenet.classifier = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(mobilenet.last_channel, num_classes),
    )

    # Prepare for training
    if use_gpu:
        mobilenet.cuda()
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')

    optimizer = optim.Adam(
        mobilenet.classifier.parameters(),
        lr=lr,
        betas=betas,
        eps=eps,
        weight_decay=weight_decay,
    )
    loss_func = nn.CrossEntropyLoss()
    scheduler = optim.lr_scheduler.StepLR(
        optimizer,
        step_size=step_size,
        gamma=gamma
    )

    # Train, test
    weights, train_loss, train_acc, val_loss, val_acc, _, _ = train_validate_test(
        epochs, mobilenet, optimizer, scheduler,
        loss_func, train_dl, val_dl, test_dl, device
    )

    # Save results
    write_to_csv(train_loss, 'train_loss.csv')
    write_to_csv(train_acc, 'train_acc.csv')
    write_to_csv(val_loss, 'val_loss.csv')
    write_to_csv(val_acc, 'val_acc.csv')
    torch.save(weights, path_to_save_model)