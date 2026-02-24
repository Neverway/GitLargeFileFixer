import asyncio
from nicegui import ui

file_inputs = []

async def write_to_terminal(stream: asyncio.StreamReader) -> None:
    """Just writes stuff out to the web terminal, it's all on the tin bby!"""
    while chunk := await stream.read(128):
        terminal.write(chunk)

async def run_command(cmd: list[str], cwd: str) -> bool:
    """Run a command, stream output to terminal, return True on success"""
    terminal.writeln(f'\x1b[33m$ {" ".join(cmd)}\x1b[0m')
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.gather(
        write_to_terminal(process.stdout),
        write_to_terminal(process.stderr),
        process.wait(),
    )
    if process.returncode != 0:
        terminal.writeln(f'\x1b[31mCommand failed with exit code {process.returncode}\x1b[0m')
        return False
    return True

async def run_subprocess():
    """Runs through the whole process of tracking, restaging, and committing the problematic files (This is run when you hit the button)"""
    # This code sucks and I need to clean it up later, but that is a problem for future me! ~ Liz
    # Future Liz, please add a check so that if the working tree is clean, just push and return a success anyway ~Liz
    button.disable()
    terminal.writeln('\x1b[34m--- Starting LFFS ---\x1b[0m')

    paths = [i.value.strip() for i in file_inputs if i.value.strip()]
    proj  = projectPath.value.strip()
    msg   = commitMessage.value.strip()
    br    = branch.value.strip()
    user  = username.value.strip()
    pwd   = password.value.strip()

    # Basic validation
    if not proj:
        terminal.writeln('\x1b[31mThe project path is required! (This is the path to your local repository)\x1b[0m')
        button.enable()
        return
    if not paths:
        terminal.writeln('\x1b[31mAt least one problem file path is required! (This is relative to the repository, not to your drive)\x1b[0m')
        button.enable()
        return
    if not br:
        terminal.writeln('\x1b[31mA branch name is required! (Enter whatever branch you are currently on)\x1b[0m')
        button.enable()
        return
    if not msg:
        terminal.writeln('\x1b[31mA commit message is required!\x1b[0m')
        button.enable()
        return

    # Step 1: Track each problem file with git lfs
    terminal.writeln('\x1b[34m[Step 1/6] Tracking problem files with git lfs...\x1b[0m')
    for path in paths:
        if not await run_command(['git', 'lfs', 'track', path], cwd=proj):
            button.enable()
            return

    # Step 2: Add .gitattributes
    terminal.writeln('\x1b[34m[Step 2/6] Adding .gitattributes...\x1b[0m')
    if not await run_command(['git', 'add', '.gitattributes'], cwd=proj):
        button.enable()
        return

    # Step 3: Commit
    terminal.writeln('\x1b[34m[Step 3/6] Committing changes...\x1b[0m')
    if not await run_command(['git', 'commit', '-m', msg], cwd=proj):
        button.enable()
        return

    # Step 4: Migrate each problem file
    terminal.writeln('\x1b[34m[Step 4/6] Rewriting commits with git lfs migrate...\x1b[0m')
    for path in paths:
        if not await run_command(['git', 'lfs', 'migrate', 'import', f'--include={path}'], cwd=proj):
            button.enable()
            return

    # Step 5: Confirm tracked files
    terminal.writeln('\x1b[34m[Step 5/6] Confirming tracked files...\x1b[0m')
    if not await run_command(['git', 'lfs', 'ls-files'], cwd=proj):
        button.enable()
        return

    # Step 6: Force push — embed credentials in the remote URL if provided
    terminal.writeln('\x1b[34m[Step 6/6] Force pushing to remote...\x1b[0m')
    if user and pwd:
        # Get the current remote URL, inject credentials, push, then restore
        get_url = await asyncio.create_subprocess_exec(
            'git', 'remote', 'get-url', 'origin',
            cwd=proj,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        url_out, _ = await get_url.communicate()
        original_url = url_out.decode().strip()

        if original_url.startswith('https://'):
            authed_url = original_url.replace('https://', f'https://{user}:{pwd}@')
        else:
            authed_url = original_url  # SSH or other — credentials won't be injected

        await run_command(['git', 'remote', 'set-url', 'origin', authed_url], cwd=proj)
        success = await run_command(['git', 'push', 'origin', br, '--force'], cwd=proj)
        await run_command(['git', 'remote', 'set-url', 'origin', original_url], cwd=proj)  # always restore

        if not success:
            button.enable()
            return
    else:
        if not await run_command(['git', 'push', 'origin', br, '--force'], cwd=proj):
            button.enable()
            return

    terminal.writeln('\x1b[32mMishon Compree! Your files are now tracked via LFS!\x1b[0m')
    button.enable()

def add_file_input():
    """Add another problem file selection field"""
    with file_container:
        with ui.row().style('width: 100%; align-items: center;') as row:
            inp = ui.input(placeholder='path/to/your/file.owo').style('flex: 1;')
            ui.button(icon='close', on_click=lambda r=row, i=inp: remove_file_input(r, i)).props('flat round dense')
            file_inputs.append(inp)

def remove_file_input(row, inp):
    """Remove a problem file selection field"""
    if inp in file_inputs:
        file_inputs.remove(inp)
    row.delete()

# Page settings
ui.page_title("Git Large File Fixer Storage")
ui.dark_mode(True)

# Title
ui.skeleton().classes('w-full')
ui.image("Icon.png").style('width: 160px; image-rendering: pixelated;')

# Output terminal and welcome message
terminal = ui.xterm({'cols': 100, 'rows': 9, 'covertEol': True}).style('width: 100%;')
terminal.writeln('\x1b[34mWelcome to LFFS! :3\x1b[0m')
terminal.writeln('\x1b[34mAwaiting user input...\x1b[0m')

# About page stuff
# Future Liz, Please add an FAQ/Help page and switch this from an expansion to tabs
with ui.expansion('What is this?', icon='work').classes('w-full'):
    ui.label("Normally to fix a file in your project that became to large, and now needs Git LFS, you'd need to:").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("1.) Track the problem file with it's exact path `git lfs track Path/To/Your/File.owo`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("2.) Add the newly created lfs attributes file `git add .gitattributes`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("3.) Commit changes`git commit -m 'Tracked FILE NAME with git lfs'`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("4.) Rewrite commits containing that file to have a pointer in its place`git lfs migrate import --include='Path/To/Your/File.owo'`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("5.) Confirm tracked files `git lfs ls-files`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("6.) Force push your branch to overwrite history`git push origin Your-Branch-Name --force`").style('color: #555555; font-size: 100%; font-weight: 300')
    ui.label("This program does all of that for you though! Just fill out the fields below! :3").style('color: #555555; font-size: 100%; font-weight: 300')

# Username and Token
with ui.splitter().style('width: 100%;') as splitter:
    with splitter.before:
        username = ui.input(label='Git Username', placeholder='Username').style('width: 100%;')
    with splitter.after:
        password = ui.input(label='Git Password', placeholder='OAuth Token', password=True).style('width: 100%;')

# Path and Branch
with ui.splitter().style('width: 100%;') as splitter:
    with splitter.before:
        projectPath = ui.input(label='Path to project', placeholder='path/to/your/project').style('width: 100%;')
    with splitter.after:
        branch = ui.input(label='Current repo branch', placeholder='Branch name (eg. develop)').style('width: 100%;')

# Problem file selector
with ui.expansion('Problem Files', icon='folder', value=True).classes('w-full'):
    file_container = ui.column().style('width: 100%;')
    add_file_input()
    ui.button('+ Add Problem File', on_click=add_file_input).props('flat')

# Commit message and Fix button
commitMessage = ui.input(label='Commit message', placeholder='Tracked FILENAME with git lfs').style('width: 100%;')
button = ui.button("Fix Tracked Files", on_click=run_subprocess).style('width: 100%;')

ui.run()