import asyncio
from bot.image import render_matrix

async def main():
    matrix = {(200, 20): 10, (600, 80): 5, (800, 90): 2, (300, 0): 1}
    img_bytes = await render_matrix(matrix, sklad_id=1, eni=120)
    with open('test_sklad_image.png', 'wb') as f:
        f.write(img_bytes)
    print("test_sklad_image.png created successfully!")

if __name__ == '__main__':
    asyncio.run(main())
