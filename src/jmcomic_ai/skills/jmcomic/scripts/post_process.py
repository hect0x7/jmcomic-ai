import argparse
import sys
from pathlib import Path



from jmcomic_ai.core import JmcomicService


def main():
    parser = argparse.ArgumentParser(description="Post-process downloaded JMComic albums (Zip, PDF, LongImg)")
    parser.add_argument("--id", required=True, help="Album ID to process")
    parser.add_argument("--type", required=True, choices=["zip", "img2pdf", "long_img"], help="Processing type")
    parser.add_argument("--option", help="Path to option.yml")
    parser.add_argument("--delete", action="store_true", help="Delete original files after processing")
    parser.add_argument("--password", help="Password for encryption (Zip/PDF)")
    parser.add_argument("--outdir", help="Output directory")

    args = parser.parse_args()

    service = JmcomicService(args.option)

    params = {}
    if args.delete:
        params["delete_original_file"] = True
    if args.password:
        if args.type == "long_img":
            parser.error("--password is only supported for zip or img2pdf")
        params["encrypt"] = {"password": args.password}

    # Map outdir to correct plugin parameter
    if args.outdir:
        if args.type == "zip":
            params["zip_dir"] = args.outdir
        elif args.type == "img2pdf":
            params["pdf_dir"] = args.outdir
        elif args.type == "long_img":
            params["img_dir"] = args.outdir

    result = service.post_process(args.id, args.type, params)
    print(result)


if __name__ == "__main__":
    main()
