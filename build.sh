#!/bin/sh 

BUILD_CMD="pyinstaller -n ani-tupi --onefile main.py --add-data plugins:plugins --hidden-import plugins "
for plugin in `eval "ls plugins/*.py | sed 's/\.py//' | sed 's/\//\./' | sed 's/plugins.__init__//'"`
do 
	BUILD_CMD+=" --hidden-import ${plugin}"
done
echo "${BUILD_CMD}"
$BUILD_CMD

PLUGIN_CP="cp -r plugins dist"
echo "${PLUGIN_CP}"
$PLUGIN_CP