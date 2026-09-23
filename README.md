# Candlestack

Configurable pipeline for pattern analysis in financial time series.

Team project at the Faculty of Electrical Engineering and Information Technology,
Slovak University of Technology in Bratislava (STU FEI).

## About

Candlestack is a modular experimentation environment for financial time series.
In a web interface the user assembles a full experiment from three interchangeable layers:

1. **Preprocessing and data representation**: Renko, Kagi, time windows, normalization, segmentation.
2. **Model**: upload and run a trained `.keras` model, with input/output shape validation
   against the chosen preprocessing.
3. **Post-processing and decision**: thresholding, smoothing, clustering, holding period,
   position sizing and risk limits, which turn predictions into trading signals.

Every run produces an experiment with a unified set of metrics and visualizations,
so that runs can be compared to find which combination of representation, architecture
and post-processing gives the most stable results.

## Status

Early setup. Project structure and run instructions will follow.
