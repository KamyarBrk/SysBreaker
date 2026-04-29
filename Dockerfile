FROM python:3.12

ADD Official_Supervisor.py .
ADD Setup_Scripts/requirements.txt .
ADD vector/* ./vector/
ADD Tools/* ./Tools/
ADD Supervisor/Supervisor_Memory/* ./Supervisor/Supervisor_Memory/
ADD tmp/Plans ./tmp/
ADD tmp/Reports ./tmp/

RUN pip install -r requirements.txt

ENTRYPOINT ["streamlit", "run", "Official_Supervisor.py"]