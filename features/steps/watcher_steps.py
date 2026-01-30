from behave import when


@when("the watcher scans for new files")
def step_when_watcher_scans(context):
    # Simulate watcher logic: move file from input to staging and update DB
    import os
    import shutil
    from app.models.media import MediaItem, FileState, MediaType
    import asyncio

    async def watcher():
        async with context.db() as session:
            for filename in os.listdir(context.input_dir):
                src = os.path.join(context.input_dir, filename)
                dst = os.path.join(context.staging_dir, filename)
                shutil.move(src, dst)
                item = MediaItem(
                    source_path=filename,
                    state=FileState.scanned,
                    media_type=MediaType.music,
                )
                session.add(item)
            await session.commit()

    asyncio.run(watcher())
