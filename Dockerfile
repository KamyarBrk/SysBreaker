FROM python:3.12

ADD Official_Supervisor.py .
ADD Setup_Scripts/requirements.txt .
ADD vector/* ./vector/
ADD Tools/* ./Tools/
ADD Supervisor/Supervisor_Memory/* ./Supervisor/Supervisor_Memory/
ADD tmp/Plans ./tmp/
ADD tmp/Reports ./tmp/

EXPOSE 11434
RUN pip install -r requirements.txt
CMD ["python", "./Official_Supervisor.py"]