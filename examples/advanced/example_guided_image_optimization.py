"""
Guided image optimization
=========================

This example showcases how a guided, i.e. regionally constraint, NST can be performed
in ``pystiche``.

Usually, the ``style_loss`` discards spatial information since the style elements
should be able to be synthesized regardless of their position in the
``style_image``. Especially for images with clear separated regions style elements
might leak into regions where they fit well with respect to the perceptual loss, but
don't belong for a human observer. This can be overcome with spatial constraints also
called ``guides`` (:cite:`GEB+2017`).
"""


########################################################################################
# We start this example by importing everything we need and setting the device we will
# be working on.

import pystiche
from pystiche import demo, enc, loss, optim
from pystiche.image import guides_to_segmentation, show_image
from pystiche.misc import get_device, get_input_image

print(f"I'm working with pystiche=={pystiche.__version__}")

device = get_device()
print(f"I'm working with {device}")


########################################################################################
# In a first step we load and show the images that will be used in the NST.

images = demo.images()
images.download()
size = 500

########################################################################################

content_image = images["castle"].read(size=size, device=device)
show_image(content_image)


########################################################################################

style_image = images["church"].read(size=size, device=device)
show_image(style_image)


########################################################################################
# Unguided image optimization
# ---------------------------
#
# As a baseline we use a default NST with a
# :class:`~pystiche.loss.FeatureReconstructionLoss` as ``content_loss`` and
# :class:`~pystiche.loss.GramLoss` s as ``style_loss``.

multi_layer_encoder = enc.vgg19_multi_layer_encoder()

content_layer = "relu4_2"
content_encoder = multi_layer_encoder.extract_encoder(content_layer)
content_weight = 1e0
content_loss = loss.FeatureReconstructionLoss(
    content_encoder, score_weight=content_weight
)

style_layers = ("relu1_1", "relu2_1", "relu3_1", "relu4_1", "relu5_1")
style_weight = 1e4


def get_style_op(encoder, layer_weight):
    return loss.GramLoss(encoder, score_weight=layer_weight)


style_loss = loss.MultiLayerEncodingLoss(
    multi_layer_encoder, style_layers, get_style_op, score_weight=style_weight,
)


perceptual_loss = loss.PerceptualLoss(content_loss, style_loss).to(device)
print(perceptual_loss)


########################################################################################
# We set the target images for the optimization ``criterion``.

perceptual_loss.set_content_image(content_image)
perceptual_loss.set_style_image(style_image)


########################################################################################
# We perform the unguided NST and show the result.

starting_point = "content"
input_image = get_input_image(starting_point, content_image=content_image)

output_image = optim.image_optimization(input_image, perceptual_loss, num_steps=500)


########################################################################################

show_image(output_image)


########################################################################################
# While the result is not completely unreasonable, the building has a strong blueish
# cast that looks unnatural. Since the optimization was unconstrained the color of the
# sky was used for the building. In the remainder of this example we will solve this by
# dividing the images in multiple separate regions.


########################################################################################
# Guided image optimization
# -------------------------
#
# For both the ``content_image`` and ``style_image`` we load regional ``guides`` and
# show them.
#
# .. note::
#
#   In ``pystiche`` a ``guide`` is a binary image in which the white pixels make up the
#   region that is guided. Multiple ``guides`` can be combined into a ``segmentation``
#   for a better overview. In a ``segmentation`` the regions are separated by color.
#   You can use :func:`~pystiche.image.guides_to_segmentation` and
#   :func:`~pystiche.image.segmentation_to_guides` to convert one format to the other.
#
# .. note::
#
#   The guides used within this example were created manually. It is possible to
#   generate them automatically :cite:`CZP+2018`, but this is outside the scope of
#   ``pystiche``.

content_guides = images["castle"].guides.read(size=size, device=device)
content_segmentation = guides_to_segmentation(content_guides)
show_image(content_segmentation, title="Content segmentation")


########################################################################################

style_guides = images["church"].guides.read(size=size, device=device)
style_segmentation = guides_to_segmentation(style_guides)
show_image(style_segmentation, title="Style segmentation")

########################################################################################
# The ``content_image`` is separated in three ``regions``: the ``"building"``, the
# ``"sky"``, and the ``"water"``.
#
# .. note::
#
#   Since no water is present in the style image we reuse the ``"sky"`` for the
#   ``"water"`` region.

regions = ("building", "sky", "water")

style_guides["water"] = style_guides["sky"]


########################################################################################
# Since the stylization should be performed for each region individually, we also need
# separate losses. Within each region we use the same setup as before. Similar to
# how a :class:`~pystiche.loss.MultiLayerEncodingLoss` bundles multiple
# operators acting on different layers a :class:`~pystiche.loss.MultiRegionLoss`
# bundles multiple losses acting in different regions.
#
# The guiding is only needed for the ``style_loss`` since the ``content_loss`` by
# definition honors the position of the content during the optimization. Thus, the
# previously defined ``content_loss`` is combined with the new regional ``style_loss``.


def get_region_op(region, region_weight):
    return loss.MultiLayerEncodingLoss(
        multi_layer_encoder, style_layers, get_style_op, score_weight=region_weight,
    )


style_loss = loss.MultiRegionLoss(regions, get_region_op, score_weight=style_weight)

perceptual_loss = loss.PerceptualLoss(content_loss, style_loss).to(device)
print(perceptual_loss)


########################################################################################
# The ``content_loss`` is unguided and thus the content image can be set as we did
# before. For the ``style_loss`` we use the same ``style_image`` for all regions and
# only vary the guides.

perceptual_loss.set_content_image(content_image)

for region in regions:
    perceptual_loss.set_style_image(
        style_image, guide=style_guides[region], region=region
    )
    perceptual_loss.set_content_guide(content_guides[region], region=region)


########################################################################################
# We rerun the optimization with the new constrained optimization ``criterion`` and
# show the result.

starting_point = "content"
input_image = get_input_image(starting_point, content_image=content_image)

output_image = optim.image_optimization(input_image, perceptual_loss, num_steps=500)


########################################################################################

show_image(output_image)


########################################################################################
# With regional constraints we successfully removed the blueish cast from the building
# which leads to an overall higher quality. Unfortunately, reusing the sky region for
# the water did not work out too well: due to the vibrant color, the water looks
# unnatural.
#
# Fortunately, this has an easy solution. Since we are already using separate losses
# for each region we are not bound to use only a single ``style_image``: if required,
# we can use a different ``style_image`` for each region.


########################################################################################
# Guided image optimization with multiple styles
# ----------------------------------------------
#
# We load a second style image that has water in it.

second_style_image = images["cliff"].read(size=size, device=device)
show_image(second_style_image, "Second style image")

########################################################################################

second_style_guides = images["cliff"].guides.read(size=size, device=device)
show_image(guides_to_segmentation(second_style_guides), "Second style segmentation")


########################################################################################
# We can reuse the previously defined criterion and only change the ``style_image`` and
# ``style_guides`` in the ``"water"`` region.

region = "water"
perceptual_loss.set_style_image(
    second_style_image, guide=second_style_guides[region], region=region
)


########################################################################################
# Finally, we rerun the optimization again with the new constraints.

starting_point = "content"
input_image = get_input_image(starting_point, content_image=content_image)

output_image = optim.image_optimization(input_image, perceptual_loss, num_steps=500)


########################################################################################

# sphinx_gallery_thumbnail_number = 9
show_image(output_image)

########################################################################################
# Compared to the two previous results we now achieved the highest quality.
# Nevertheless, This approach has its downsides : since we are working with multiple
# images in multiple distinct regions, the memory requirement is higher compared to the
# other approaches. Furthermore, compared to the unguided NST, the guides have to be
# provided together with the for the content and style images.
