from krita import Krita, DockWidgetFactoryBase, DockWidgetFactory
from krita_diffusion.dockers.diffusion import KritaDiffusionDocker


app = Krita.instance()

dockers = [
    KritaDiffusionDocker
]

for docker in dockers:
    app.addDockWidgetFactory(DockWidgetFactory(docker.name, DockWidgetFactoryBase.DockMinimized, docker))
