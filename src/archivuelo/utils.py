from tqdm.asyncio import tqdm

class ProgressBar():
    """
    Allow item_name to be reflected dynamically, implemented as a separate progress bar
    """

    def __init__(self, name: str, **tqdm_options):
        self.bar = tqdm(
            bar_format="{desc} | {bar} | {percentage:3.0f}% | {n_fmt}/{total_fmt} [{elapsed}]",
            desc=name,
            **tqdm_options,
        )
        self.bar_current_item = tqdm(
            bar_format="    {desc}",
            leave=False,
        )
    
    def update(self, n: float, item_name: str=None):
        if n != 0:
            # If only item_name is being updated with 0 progress, don't call tqdm.update()
            self.bar.update(n)
        if item_name:
            self.bar_current_item.set_description_str(item_name)