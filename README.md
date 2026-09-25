# Prerequisites
You'll need *at least* Python 3.11 and Pip 20.3
(this code was developed in Python 3.13.11 and Pip 26.0.1)

Change cwd to the `/CS907Submission/` folder </br>
Run `python3 -m venv venv` or `python -m venv venv` </br>
Run `source venv/bin/activate` for Linux and `./venv/Scripts/Activate.ps1` for Windows. </br>

Then install the modules: `pip install -r requirements.txt`</br>


# Steps to Reproduce
Change current working directory to `/CS907Submission/`</br>
Run `main.py` **from the /CS907Submission/ folder**: `python main.py`</br>

**NOTE: Running the simulations again WILL overwrite the pre-existing results. These results are for the big simulation that takes approx ~40 hours. The program is set to automatically execute a 'showcase' simulation which takes ~1 minute to run.**</br>
- If you would like to retrieve the old, large simulation results after executing `python main.py`, they are backed up in `./.REALRESULTS_BACKUP/`
