"""AI engines for the Wildlife Population Intelligence System.

Three pretrained models, all PyTorch, all loaded lazily:

  yolov8n-coco        animal detection, counting, bounding boxes
  resnet50-imagenet   species classification of each detected animal
  ast-audioset        acoustic event classification for audio recordings

Every label these models emit is recorded with the model's own confidence and
the taxonomic rank the label actually resolves to. Where a model can only say
"bird", the platform stores "bird" at coarse rank -- it never promotes a coarse
label to a species identification.
"""
