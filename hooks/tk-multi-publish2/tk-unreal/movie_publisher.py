"""
Hook for publishing movies from Unreal Engine to Shotgun.
"""
import sgtk
import os

HookBaseClass = sgtk.get_hook_baseclass()

class MoviePublisher(HookBaseClass):
    """
    Hook for publishing movies to Shotgun.
    """

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin.
        """
        if item.type == "unreal.movie":
            return True
            
        return False

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.
        """
        # Make sure we have a valid movie file
        movie_path = item.properties.get("movie_path")
        if not movie_path or not os.path.exists(movie_path):
            self.logger.warning("Movie file does not exist: %s" % movie_path)
            return False
            
        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        """
        publisher = self.parent
        
        # Get the path to publish
        publish_template = self.get_template_by_name(settings["Publish Template"])
        publish_path = publish_template.apply_fields(item.properties)
        
        # Ensure the publish folder exists
        self._ensure_folder_exists(publish_path)
        
        # Copy the movie file to the publish location
        self._copy_movie_file(item.properties["movie_path"], publish_path)
        
        # Register the publish
        publish_data = {
            "tk": publisher.sgtk,
            "context": item.context,
            "comment": item.description,
            "path": publish_path,
            "name": item.name,
            "version_number": item.properties.get("version_number", 1),
            "thumbnail_path": item.get_thumbnail_as_path(),
            "published_file_type": "Movie"
        }
        
        # Register the publish using the base class' utility method
        super(MoviePublisher, self)._register_publish(**publish_data)
        
        return True

    def _ensure_folder_exists(self, path):
        """
        Ensure the folder exists for the given path.
        """
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)
            
    def _copy_movie_file(self, source_path, target_path):
        """
        Copy the movie file to the publish location.
        """
        import shutil
        shutil.copy2(source_path, target_path)