"""Generates the real and fake QR images for your demo."""
import qrcode

qrcode.make("upi://pay?pa=sharmageneral@paytm&pn=Sharma General Store").save("real_qr.png")
qrcode.make("upi://pay?pa=sharmageneral@xyz&pn=Sharma General Store").save("fake_qr.png")
print("Created real_qr.png and fake_qr.png")
