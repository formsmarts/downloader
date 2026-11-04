"""macOS date formatting/parsing in the user's regional format, and the
native graphical date picker (NSDatePicker) shown in a small panel."""

from datetime import date

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSDatePicker,
    NSDatePickerElementFlagYearMonthDay,
    NSDatePickerStyleClockAndCalendar,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
)
from Foundation import (
    NSCalendar,
    NSCalendarUnitDay,
    NSCalendarUnitMonth,
    NSCalendarUnitYear,
    NSDateComponents,
    NSDateFormatter,
    NSLocale,
    NSObject,
)


def calendar_icon_png(point_size: float = 13.0) -> bytes:
    """Apple's "calendar" SF Symbol as PNG data, tinted for the current
    light/dark appearance (macOS 11+)."""
    from AppKit import (
        NSApp,
        NSAppearanceNameAqua,
        NSAppearanceNameDarkAqua,
        NSBitmapImageRep,
        NSColor,
        NSCompositingOperationSourceAtop,
        NSGraphicsContext,
        NSImage,
        NSImageSymbolConfiguration,
        NSPNGFileType,
        NSRectFillUsingOperation,
    )

    image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        "calendar", "Choose a date"
    )
    if image is None:
        raise RuntimeError("SF Symbols aren't available")
    image = image.imageWithSymbolConfiguration_(
        NSImageSymbolConfiguration.configurationWithPointSize_weight_(point_size, 0.0)
    )
    w, h = image.size().width, image.size().height
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, int(round(w)), int(round(h)), 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0
    )
    dark = (
        NSApp() is not None
        and NSApp().effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [NSAppearanceNameAqua, NSAppearanceNameDarkAqua]
        ) == NSAppearanceNameDarkAqua
    )
    gray = 0.85 if dark else 0.25
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    image.drawInRect_(NSMakeRect(0, 0, w, h))
    NSColor.colorWithWhite_alpha_(gray, 1.0).set()
    NSRectFillUsingOperation(NSMakeRect(0, 0, w, h), NSCompositingOperationSourceAtop)
    ctx.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    return bytes(rep.representationUsingType_properties_(NSPNGFileType, {}))


def _formatter():
    fmt = NSDateFormatter.alloc().init()
    fmt.setLocale_(NSLocale.autoupdatingCurrentLocale())
    # Numeric date with a 4-digit year, ordered as in the user's region
    # (e.g. 10/31/2026, 31/10/2026, 31.10.2026, 2026/10/31).
    fmt.setLocalizedDateFormatFromTemplate_("yyyyMMdd")
    fmt.setLenient_(False)
    return fmt


def _to_nsdate(d: date):
    comps = NSDateComponents.alloc().init()
    comps.setYear_(d.year)
    comps.setMonth_(d.month)
    comps.setDay_(d.day)
    comps.setHour_(12)  # midday: no DST edge cases
    return NSCalendar.currentCalendar().dateFromComponents_(comps)


def _from_nsdate(ns) -> date:
    comps = NSCalendar.currentCalendar().components_fromDate_(
        NSCalendarUnitYear | NSCalendarUnitMonth | NSCalendarUnitDay, ns
    )
    return date(comps.year(), comps.month(), comps.day())


def format_date(d: date) -> str:
    return str(_formatter().stringFromDate_(_to_nsdate(d)))


def parse_date(text: str):
    ns = _formatter().dateFromString_(text.strip())
    if ns is None:
        return None
    d = _from_nsdate(ns)
    if d.year < 100:  # a 2-digit year was typed
        d = d.replace(year=2000 + d.year)
    return d


class _PickerController(NSObject):
    """Target of the date picker, Done button and panel delegate."""

    def initWithCallback_(self, callback):
        self = objc.super(_PickerController, self).init()
        if self is None:
            return None
        self.callback = callback
        self.panel = None
        return self

    def dateChanged_(self, sender):
        self.callback(_from_nsdate(sender.dateValue()))

    def done_(self, sender):
        self.close()

    def windowDidResignKey_(self, notification):
        self.close()

    def windowWillClose_(self, notification):
        self.panel = None

    def close(self):
        panel, self.panel = self.panel, None
        if panel is not None:
            panel.setDelegate_(None)
            panel.orderOut_(None)


_active = None  # keeps the controller alive while its panel is shown


def show_picker(initial: date, screen_x: int, screen_y: int, on_change):
    """Show the native calendar under the given point (Tk screen coordinates,
    origin top-left). on_change(date) is called whenever the user picks a
    date. The panel closes on Done or when it loses focus."""
    global _active
    if _active is not None:
        _active.close()

    controller = _PickerController.alloc().initWithCallback_(on_change)

    picker = NSDatePicker.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    picker.setDatePickerStyle_(NSDatePickerStyleClockAndCalendar)
    picker.setDatePickerElements_(NSDatePickerElementFlagYearMonthDay)
    picker.setBezeled_(False)
    picker.setDrawsBackground_(False)
    picker.setLocale_(NSLocale.autoupdatingCurrentLocale())
    picker.setDateValue_(_to_nsdate(initial))
    picker.setTarget_(controller)
    picker.setAction_("dateChanged:")
    picker.sizeToFit()
    pw, ph = picker.frame().size.width, picker.frame().size.height

    button = NSButton.buttonWithTitle_target_action_("Done", controller, "done:")
    button.setKeyEquivalent_("\r")
    button.sizeToFit()
    bw, bh = button.frame().size.width, button.frame().size.height

    pad = 10
    width = max(pw, bw) + 2 * pad
    height = ph + bh + 3 * pad
    picker.setFrameOrigin_((pad, bh + 2 * pad))
    button.setFrameOrigin_((width - bw - pad, pad))

    screen_h = NSScreen.screens()[0].frame().size.height
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(screen_x, screen_h - screen_y - height, width, height),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskUtilityWindow,
        NSBackingStoreBuffered,
        False,
    )
    panel.setTitle_("Choose a date")
    panel.setFloatingPanel_(True)
    panel.setHidesOnDeactivate_(True)
    panel.setReleasedWhenClosed_(False)
    panel.contentView().addSubview_(picker)
    panel.contentView().addSubview_(button)
    panel.setDelegate_(controller)
    controller.panel = panel
    _active = controller
    panel.makeKeyAndOrderFront_(None)
    panel.makeFirstResponder_(picker)
