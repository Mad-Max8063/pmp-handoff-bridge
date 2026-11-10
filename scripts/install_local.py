"""Install into a NEW isolated Hermes home. Does not start Hermes or a model."""
import argparse,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PLUGIN_FILES=('plugin.yaml','__init__.py','LICENSE','PROVENANCE.md')
def install(home):
 home=Path(home).expanduser().absolute()
 if home.exists(): raise ValueError('Home already exists; choose a new empty destination. Nothing overwritten.')
 home.mkdir(parents=True,exist_ok=False)
 target=home/'plugins'/'pmp-handoff-bridge';target.mkdir(parents=True)
 for name in PLUGIN_FILES: shutil.copyfile(ROOT/name,target/name)
 shutil.copytree(ROOT/'bridge',target/'bridge',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 config={'plugins':{'enabled':['pmp-handoff-bridge']},'tools':{'tool_search':{'enabled':'off'}}}
 with (home/'config.yaml').open('x',encoding='utf-8') as f: json.dump(config,f,indent=2)
 print(json.dumps({'status':'INSTALLED_NOT_STARTED','home':str(home),'plugin':str(target),'model_calls':0},indent=2))
 return target
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--home',required=True)
 install(p.parse_args().home)