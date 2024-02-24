"use client";

import Nav from "./Nav";
import gp_logo from "/src/images/logo.svg";
import { classMerge } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";

export default function SiteHeader({
    tallHeader = false,
}: {
    tallHeader: boolean;
}) {
    return (
        <header
            id="site_header"
            className={classMerge(
                "fixed top-0 left-0 w-full z-[100] bg-header-gray shadow-[0_1px_20px_1px_#777] px-4 py-2 h-[70px]",
                tallHeader && "lg:h-[120px]"
            )}
        >
            <div className="flex justify-center items-center w-full max-w-screen-xl mx-auto">
                <Link
                    href="/"
                    className={classMerge(
                        "relative w-[250px] h-[53px]",
                        tallHeader && "lg:h-[100px]"
                    )}
                >
                    <Image
                        className="object-contain object-left-top"
                        src={gp_logo}
                        alt="Gamers' Plane Logo"
                        fill={true}
                    />
                </Link>
                <Nav />
            </div>
        </header>
    );
}
