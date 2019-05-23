FROM gcr.io/google-appengine/python
LABEL python_version=python3.5

# Create a virtualenv for dependencies. This isolates these packages from
# system-level packages.
RUN virtualenv --no-download /env -p python3.5

# Set virtualenv environment variables. This is equivalent to running
# source /env/bin/activate
ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

# Copy the application's requirements.txt and run pip to install all
# dependencies into the virtualenv.
ADD requirements.txt /app/
RUN pip install -r /app/requirements.txt

# Add the application source code.
ADD . /app/

# Replace certain zipline lib files with custom ones
RUN cp /app/replacement/calendar_utils.py $(python -c "from trading_calendars import calendar_utils as _; import os; print(os.path.dirname(_.__file__))")
RUN cp /app/replacement/core.py $(python -c "from zipline.data.bundles import core as _; import os; print(os.path.dirname(_.__file__))")
RUN cp /app/replacement/minute_bars.py $(python -c "from zipline.data import minute_bars as _; import os; print(os.path.dirname(_.__file__))")

# Run a WSGI server to serve the application.
CMD gunicorn --workers=3 --timeout=300 --bind=:$PORT backtester.wsgi
