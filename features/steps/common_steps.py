import os
from behave import given, then

@given('a file "{filename}" exists in the input directory')
def step_given_file_in_input(context, filename):
    file_path = os.path.join(context.input_dir, filename)
    with open(file_path, "w") as f:
        f.write("test content")
    context.last_file = filename

@then('the database should show the file "{filename}" in "{state}" state')
def step_then_db_file_state(context, filename, state):
    from sqlalchemy.future import select
    from app.models.media import MediaItem
    import asyncio
    async def check():
        async with context.db() as session:
            result = await session.execute(select(MediaItem).where(MediaItem.source_path == filename))
            item = result.scalar_one_or_none()
            assert item is not None, f"File {filename} not found in DB"
            assert item.state == state, f"Expected {state}, got {item.state}"
    asyncio.run(check())
