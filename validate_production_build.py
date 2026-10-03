"""Prueba el EXE de cliente mediante sus comprobaciones de arranque preexistentes."""
import hashlib,json,os,subprocess,winreg
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import suite_trial_state as state


def main():
    root=Path(__file__).resolve().parent
    exe=root/'dist/professional_licensed_main.dist/Eleuthera Professional Plus.exe'
    out=root/'test-results/final/build-validation'
    profile=out/'production-profile';profile.mkdir(exist_ok=True)
    license_file=profile/'Team Eleuthera/CinemaProfessionalPlus/license.json';license_file.parent.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,LOCALAPPDATA=str(profile),QT_QPA_PLATFORM='offscreen')
    trial=(out/'trial.ecplic').read_bytes();payload=json.loads(trial)['payload']
    identity=payload['product']+':'+payload['machine']+':'+payload['license_id']
    identifier=hashlib.sha256(identity.encode()).hexdigest()
    activation=license_file.parent/'Activation'
    passed=[]
    def start(name,raw):
        license_file.write_bytes(raw);target=out/(name+'.json')
        run=subprocess.run([str(exe),'--check-startup',str(target)],cwd=exe.parent,env=env,timeout=90)
        assert run.returncode==0 and target.exists(),name
        data=json.loads(target.read_text(encoding='utf-8'))
        assert data['edition']=='professional' and 'Presupuesto' in data['tabs']
        assert target.with_suffix('.xlsx').exists() and target.with_suffix('.pdf').exists()
        passed.append(name)
    try:
        start('production-perpetual',(out/'perpetual.ecplic').read_bytes())
        start('production-trial-first',trial)
        first=json.loads(state.protect((activation/(identifier+'.dat')).read_bytes(),decrypt=True))['first_activation']
        start('production-trial-reopen',trial)
        assert json.loads(state.protect((activation/(identifier+'.dat')).read_bytes(),decrypt=True))['first_activation']==first
        # Simulate retained expired activation; never alter the Windows clock.
        now=datetime.now(timezone.utc)
        saved=dict(version=1,identity=identity,first_activation=(now-timedelta(days=4)).isoformat(),last_seen=now.isoformat())
        with patch.object(state,'state_directory',return_value=activation):
            state.write_copies(identifier,state.protect(json.dumps(saved).encode()))
        target=out/'production-expired-must-not-start.json'
        process=subprocess.Popen([str(exe),'--check-startup',str(target)],cwd=exe.parent,env=env)
        try:
            from time import monotonic,sleep
            deadline=monotonic()+30;title=''
            while monotonic()<deadline and process.poll() is None:
                # Read-only process metadata; no injected Windows UI input.
                title=subprocess.check_output(['powershell','-NoProfile','-Command',f'(Get-Process -Id {process.pid}).MainWindowTitle'],text=True).strip()
                if title.startswith('Activar'):break
                sleep(0.5)
            assert process.poll() is None and title.startswith('Activar') and not target.exists(),(title,process.poll())
            passed.append('production-expired-blocked-at-activation')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=15)
        start('production-perpetual-after-expired-trial',(out/'perpetual.ecplic').read_bytes())
    finally:
        # Remove only the fresh QA license's registry value, never user activations.
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,state.state_key(),0,winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key,identifier)
        except FileNotFoundError:pass
    (out/'production-results.json').write_text(json.dumps({'passed':passed,'same_first_activation':True},indent=2))
    print('PASS: actual production EXE, both licenses, retained activation, expired block, PDF and Excel.')


if __name__=='__main__':main()
