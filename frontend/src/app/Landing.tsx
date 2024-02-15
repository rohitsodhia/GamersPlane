import logo_13thage from "@/images/logos/13thage.png";
import logo_dnd5 from "@/images/logos/dnd5.png";
import logo_fate from "@/images/logos/fate.png";
import logo_numenera from "@/images/logos/numenera.png";
import logo_pathfinder from "@/images/logos/pathfinder.png";
import logo_savageworlds from "@/images/logos/savageworlds.png";
import logo_shadowrun5 from "@/images/logos/shadowrun5.png";
import logo_starwarsffg from "@/images/logos/starwarsffg.png";
import logo_thestrange from "@/images/logos/thestrange.png";
import { classMerge } from "@/lib/utils";
import Image, { StaticImageData } from "next/image";
import Link from "next/link";

export default function Landing() {
    let numGames = 0,
        numSystems = 0,
        numPosts = 0;

    let whatIsLogos: {
            [key: string]: {
                image: StaticImageData;
                alt: string;
                twClasses: string;
                width: number;
            };
        } = {
            dnd5: {
                image: logo_dnd5,
                alt: "Dungeons &amp; Dragon's 5e logo",
                twClasses: "top-[40px] left-[34px]",
                width: 309,
            },
            thestrange: {
                image: logo_thestrange,
                alt: "The Strange logo",
                twClasses: "top-[17px] left-[387px]",
                width: 167,
            },
            pathfinder: {
                image: logo_pathfinder,
                alt: "Pathfinder logo",
                twClasses: "top-[126px] left-[82px]",
                width: 195,
            },
            starwarsffg: {
                image: logo_starwarsffg,
                alt: "Star Wars FFG logo",
                twClasses: "top-[102px] left-[336px]",
                width: 173,
            },
            "13thage": {
                image: logo_13thage,
                alt: "13th Age logo",
                twClasses: "top-[227px] left-[142px]",
                width: 89,
            },
            numenera: {
                image: logo_numenera,
                alt: "Numenera logo",
                twClasses: "top-[222px] left-[270px]",
                width: 280,
            },
            shadowrun5: {
                image: logo_shadowrun5,
                alt: "Shadowrun 5e logo",
                twClasses: "top-[331px] left-[39px]",
                width: 191,
            },
            fate: {
                image: logo_fate,
                alt: "Fate logo",
                twClasses: "top-[325px] left-[286px]",
                width: 113,
            },
            savageworlds: {
                image: logo_savageworlds,
                alt: "Savage Worlds logo",
                twClasses: "top-[295px] left-[433px]",
                width: 121,
            },
        },
        features: { icon: string; title: string; text: string }[] = [
            {
                icon: "ra-three-keys",
                title: "Any System",
                text: "Support for all table top RPGs - mainstream favorites, old classics, indie, small press and home-brew games.",
            },
            {
                icon: "ra-perspective-dice-six",
                title: "Integrated Tools",
                text: "Dedicated game forums, post as your character, integrated character sheets, dice rollers and playing cards.",
            },
            {
                icon: "ra-double-team",
                title: "Community",
                text: "A diverse and friendly community that welcomes RPG veterans and newcomers alike to the wonderful world of playing RPGs by post.",
            },
        ];

    return (
        <div>
            <div className="bg-[url('/images/landing_top_bg.jpg')] bg-bottom bg-cover">
                <div className="max-w-screen-xl mx-auto flex flex-col md:flex-row py-6">
                    <div className="backdrop-brightness-50 py-4 w-1/2 flex items-center">
                        <div>
                            <h1 className="text-white text-3xl font-bold text-center md:text-left mb-2 md:indent-16">
                                Scratch that RPG itch
                            </h1>
                            <h2 className="text-white text-lg mx-3 text-center md:text-left md:indent-24">
                                Talk and play{" "}
                                <span className="font-semibold">RPGs</span> with{" "}
                                <span className="font-semibold">
                                    hundreds of players
                                </span>
                                !
                            </h2>
                        </div>
                    </div>
                    <div className="w-1/2 p-4 bg-white [&>*]:py-2">
                        <p>
                            <span className="font-bold">{numGames}</span> active
                            games in the last month, in over{" "}
                            <span className="font-bold">{numSystems}</span>{" "}
                            systems!
                        </p>
                        <p>
                            Gamers&asop; Plane focuses on community, with{" "}
                            <span className="font-bold">{numPosts}</span> posts
                            in the last month!
                        </p>
                        <div className="[&>*]:text-center border-t border-gray-300">
                            <p>
                                Check out the <Link href="">Public Games</Link>{" "}
                                and read the adventures people have been having,
                            </p>
                            <p>or</p>
                            <p>
                                Visit the <Link href="">Games Tavern</Link> and
                                see if there&apos;s a game you&apos;re
                                interested in joining!
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            <div className="max-w-screen-xl mx-auto flex flex-col md:flex-row">
                <div className="relative h-[410px] w-[540px] box-content p-6 flex-none">
                    {Object.keys(whatIsLogos).map((system_short) => {
                        let system = whatIsLogos[system_short],
                            classes = classMerge("absolute", system.twClasses);
                        return (
                            <Image
                                key={system_short}
                                src={system.image}
                                alt={system.alt}
                                width={system.width}
                                className={classes}
                                // className="absolute"
                                // style={{ top: system.top, left: system.left }}
                            />
                        );
                    })}
                </div>
                <div className="ml-8 self-center">
                    <h2 className="font-title text-5xl">
                        What is Play-by-Post?
                    </h2>
                    <p>
                        Play-By-Post is a different way to experience tabletop
                        RPGs. Rather than dedicating a few hours at a time to
                        sit together around a table, you can play at your own
                        convenience. Log in and respond to other players and the
                        GM whenever you have a few minutes to spare.
                    </p>
                    <p>
                        Gamers&apos; Plane offers you a PbP experience you
                        won&apos;t get anywhere else, focused around a community
                        of gamers, with tools to make the experience as smooth
                        as possible. You can play with old friends, or make new
                        ones around the world!
                    </p>
                </div>
            </div>
            <div className="bg-gray-200">
                <div className="max-w-screen-xl mx-auto pt-16 pb-10 grid grid-cols-3 gap-4">
                    {features.map((feature) => {
                        let iconClasses = classMerge(
                            "ra text-4xl text-white mb-0.5",
                            feature.icon
                        );
                        return (
                            <div
                                key={feature.icon}
                                className="relative bg-white border border-gp-red px-10 pt-12 pb-6"
                            >
                                <div className="absolute left-1/2 -translate-x-1/2 top-0 -translate-y-1/2 inline-flex justify-center items-center h-16 w-16 rounded-full bg-gp-red">
                                    <i className={iconClasses}></i>
                                </div>
                                <h3 className="uppercase text-center font-title text-3xl">
                                    {feature.title}
                                </h3>
                                <p className="mb-0 text-center">
                                    {feature.text}
                                </p>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
