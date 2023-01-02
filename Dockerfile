FROM public.ecr.aws/lambda/python:3.8
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY error_logs.py .
CMD ["error_logs.lambda_handler"]