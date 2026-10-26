from pathlib import Path

from behave import given


@given('a media library root at "{root}"')
def step_impl_root(context, root):
    context.root = Path(root)
