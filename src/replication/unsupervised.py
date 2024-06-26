import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_curve
from matplotlib import pyplot as plt

from data.loading import load_nsl_kdd
from models.unsupervised import SSC_OCSVM
from preprocessing.unsupervised import preprocess_nsl_kdd

# Replication of the methodology proposed by Pu et al. in doi.org/10.26599/TST.2019.9010051

SUBSET = 'mixed'  # can be DoS, probe, r2l, u2r or mixed

train, test = load_nsl_kdd()
print('Loaded dataset')
datasets = preprocess_nsl_kdd(pd.concat([train, test]))
probe_X_train, probe_X_test, probe_y_train, probe_y_test = datasets[SUBSET]
print('Preprocessing complete')

model = SSC_OCSVM(gpus=[0, 1])

# model.fit_no_threshold(probe_y_train)
print('Training...')
model.fit(probe_X_train, probe_y_train)
print('Generating predictions...')
similarity = model.decision_function(probe_X_test)
pickle.dump(similarity, open('/mnt/d/Calvin/FYP/temp/uns_rep_sim.pkl', 'wb'))
print('Complete')
fpr, tpr, _ = roc_curve(probe_y_test == 0, similarity)
plt.plot(fpr, tpr)
plt.xlabel('FAR')
plt.ylabel('DR')
plt.title('SSC-OCSVM ROC Curve on NSL-KDD Dataset')
plt.xticks(np.arange(0, 1.1, 0.1))
plt.yticks(np.arange(0, 1.1, 0.1)) 
plt.grid(True)
plt.savefig(f'results/replication/unsupervised/{SUBSET}_roc.png')
# TODO: refactor graph code into seperate file
# print(classification_report(probe_y_test != 0, y_pred))
