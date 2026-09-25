#!/bin/zsh
set -eu
print 'NavTatva · Live AIS setup'
print 'Create an API key at https://aisstream.io, then paste it below.'
print 'The key is hidden and saved outside the project. The running app picks it up automatically.'
read -rs 'navtatva_ais_key?AISStream API key: '
print
if [[ -z "$navtatva_ais_key" ]]; then
  print 'No key entered. Nothing changed.'
  exit 1
fi
umask 077
mkdir -p "$HOME/.config/navtatva"
navtatva_key_temp=$(mktemp "$HOME/.config/navtatva/.aisstream.XXXXXX")
printf '%s' "$navtatva_ais_key" > "$navtatva_key_temp"
mv -f "$navtatva_key_temp" "$HOME/.config/navtatva/aisstream.key"
unset navtatva_ais_key
print 'Key saved. Check the Live AIS status in the app within 30 seconds.'
read -r '?Press Return to close.'
