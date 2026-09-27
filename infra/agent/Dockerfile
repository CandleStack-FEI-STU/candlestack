FROM python:3.13-alpine
# The agent uses the standard library only: pip goes, with the libraries it bundles, which the
# image scan would report.
RUN python -m pip uninstall --yes --quiet --root-user-action=ignore pip

WORKDIR /app
COPY agent.py ./

ENV PYTHONUNBUFFERED=1
USER 65534:65534
EXPOSE 8080
CMD ["python", "agent.py"]
