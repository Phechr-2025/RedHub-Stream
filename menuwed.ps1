$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
py -3 "$ScriptDir\menuwed.py" @args
