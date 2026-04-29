FROM python:3.12

ADD Official_Supervisor.py .
ADD Setup_Scripts/requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "./Official_Supervisor.py"]