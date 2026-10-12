ALTER DATABASE gamersplane CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE `acpPermissions` (
  `userID` int NOT NULL,
  `permission` varchar(20) NOT NULL,
  PRIMARY KEY (`userID`,`permission`)
);

CREATE TABLE `charAutocomplete` (
  `itemID` int NOT NULL AUTO_INCREMENT,
  `type` varchar(30) NOT NULL,
  `name` varchar(100) NOT NULL,
  `searchName` varchar(50) NOT NULL,
  `userDefined` int DEFAULT NULL,
  `approved` tinyint(1) NOT NULL DEFAULT '0',
  `approvedBy` int DEFAULT NULL,
  `approvedOn` datetime DEFAULT NULL,
  PRIMARY KEY (`itemID`),
  UNIQUE KEY `type` (`type`,`name`)
);

CREATE TABLE `charAutocomplete_systems` (
  `itemID` int NOT NULL,
  `system` varchar(200) NOT NULL,
  PRIMARY KEY (`itemID`,`system`)
);

CREATE TABLE `characterHistory` (
  `actionID` int NOT NULL AUTO_INCREMENT,
  `characterID` int NOT NULL,
  `enactedBy` int NOT NULL,
  `enactedOn` datetime NOT NULL,
  `gameID` int DEFAULT NULL,
  `action` varchar(30) NOT NULL,
  `additionalInfo` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`actionID`)
);

CREATE TABLE `characterLibrary_favorites` (
  `userID` int NOT NULL,
  `characterID` int NOT NULL,
  PRIMARY KEY (`userID`,`characterID`)
);

CREATE TABLE `characters` (
  `characterID` int NOT NULL AUTO_INCREMENT,
  `userID` int NOT NULL,
  `label` varchar(100) NOT NULL,
  `name` varchar(200) DEFAULT NULL,
  `charType` varchar(3) NOT NULL,
  `system` varchar(20) NOT NULL,
  `data` json NOT NULL,
  `gameID` int DEFAULT NULL,
  `approved` tinyint(1) NOT NULL DEFAULT '0',
  `inLibrary` tinyint(1) NOT NULL DEFAULT '0',
  `libraryViews` int NOT NULL DEFAULT '0',
  `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `retired` date DEFAULT NULL,
  PRIMARY KEY (`characterID`),
  KEY `userID` (`userID`),
  KEY `gameID` (`gameID`)
);

CREATE TABLE `contact` (
  `contactID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `date` datetime NOT NULL,
  `username` varchar(50) NOT NULL,
  `email` varchar(50) NOT NULL,
  `subject` longtext NOT NULL,
  `comment` longtext NOT NULL,
  PRIMARY KEY (`contactID`)
);

CREATE TABLE `deckDraws` (
  `drawID` int NOT NULL AUTO_INCREMENT,
  `postID` int NOT NULL,
  `deckID` int NOT NULL,
  `type` varchar(10) NOT NULL,
  `cardsDrawn` varchar(200) NOT NULL,
  `reveals` varchar(20) NOT NULL,
  `reason` varchar(50) NOT NULL,
  PRIMARY KEY (`drawID`),
  KEY `postID` (`postID`),
  KEY `deckID` (`deckID`)
);

CREATE TABLE `deckPermissions` (
  `deckID` int NOT NULL,
  `userID` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`deckID`,`userID`),
  KEY `userID` (`userID`)
);

CREATE TABLE `deckTypes` (
  `short` varchar(10) NOT NULL,
  `name` varchar(50) NOT NULL,
  `deckSize` tinyint NOT NULL,
  `class` varchar(20) NOT NULL,
  `image` varchar(20) NOT NULL,
  `extension` varchar(4) NOT NULL,
  PRIMARY KEY (`short`)
);

CREATE TABLE `decks` (
  `deckID` int NOT NULL AUTO_INCREMENT,
  `gameID` int NOT NULL,
  `label` varchar(50) NOT NULL,
  `type` varchar(10) NOT NULL,
  `deck` json NOT NULL,
  `position` tinyint NOT NULL,
  `lastShuffle` datetime NOT NULL,
  PRIMARY KEY (`deckID`),
  KEY `gameID` (`gameID`)
);

CREATE TABLE `dispatch` (
  `url` varchar(100) NOT NULL,
  `pageID` varchar(50) DEFAULT NULL,
  `ngController` varchar(50) DEFAULT NULL,
  `file` varchar(100) NOT NULL,
  `title` varchar(50) DEFAULT NULL,
  `description` mediumtext,
  `loginReq` tinyint(1) NOT NULL DEFAULT '1',
  `fixedGameMenu` tinyint NOT NULL,
  `bodyClass` varchar(50) DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `modalWidth` smallint DEFAULT NULL,
  PRIMARY KEY (`url`)
);

CREATE TABLE `faqs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `category` varchar(40) NOT NULL,
  `question` text NOT NULL,
  `answer` text NOT NULL,
  `order` int NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `featsList` (
  `featID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `searchName` varchar(50) DEFAULT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`featID`),
  UNIQUE KEY `name` (`name`)
);

CREATE TABLE `forumAdmins` (
  `userID` int NOT NULL,
  `forumID` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`userID`,`forumID`),
  KEY `forumID` (`forumID`)
);

CREATE TABLE `forumNotifications` (
  `userID` int NOT NULL,
  `threadID` int NOT NULL,
  `postID` int NOT NULL,
  `notificationType` int NOT NULL,
  PRIMARY KEY (`userID`,`threadID`,`postID`,`notificationType`)
);

CREATE TABLE `forumSubs` (
  `userID` int NOT NULL,
  `type` varchar(1) NOT NULL,
  `ID` int NOT NULL,
  PRIMARY KEY (`userID`,`type`,`ID`)
);

CREATE TABLE `forums` (
  `forumID` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `description` mediumtext,
  `forumType` varchar(1) DEFAULT 'f',
  `parentID` int DEFAULT NULL,
  `depth` int DEFAULT NULL,
  `order` int NOT NULL,
  `gameID` int DEFAULT NULL,
  `threadCount` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`forumID`),
  KEY `parentID` (`parentID`),
  KEY `depth` (`depth`) USING BTREE
);

CREATE TABLE `forums_groupMemberships` (
  `groupID` int NOT NULL,
  `userID` int NOT NULL,
  PRIMARY KEY (`groupID`,`userID`),
  KEY `userID` (`userID`)
);

CREATE TABLE `forums_groups` (
  `groupID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `status` tinyint NOT NULL DEFAULT '1',
  `ownerID` int NOT NULL,
  `gameID` int DEFAULT NULL,
  PRIMARY KEY (`groupID`),
  KEY `ownerID` (`ownerID`)
);

CREATE TABLE `forums_heritage` (
  `parentID` int NOT NULL,
  `childID` int NOT NULL,
  PRIMARY KEY (`parentID`,`childID`)
);

CREATE TABLE `forums_permissions_general` (
  `forumID` int NOT NULL,
  `read` tinyint(1) NOT NULL DEFAULT '-1',
  `write` tinyint(1) NOT NULL DEFAULT '-1',
  `editPost` tinyint(1) NOT NULL DEFAULT '-1',
  `deletePost` tinyint(1) NOT NULL DEFAULT '-1',
  `createThread` tinyint(1) NOT NULL DEFAULT '-1',
  `deleteThread` tinyint(1) NOT NULL DEFAULT '-1',
  `addPoll` tinyint(1) NOT NULL DEFAULT '-1',
  `addRolls` tinyint(1) NOT NULL DEFAULT '-1',
  `addDraws` tinyint(1) NOT NULL DEFAULT '-1',
  `moderate` tinyint(1) NOT NULL DEFAULT '-1',
  PRIMARY KEY (`forumID`)
);

CREATE TABLE `forums_permissions_groups` (
  `groupID` int NOT NULL,
  `forumID` int NOT NULL,
  `read` tinyint(1) NOT NULL DEFAULT '-2',
  `write` tinyint(1) NOT NULL DEFAULT '-2',
  `editPost` tinyint(1) NOT NULL DEFAULT '-2',
  `deletePost` tinyint(1) NOT NULL DEFAULT '-2',
  `createThread` tinyint(1) NOT NULL DEFAULT '-2',
  `deleteThread` tinyint(1) NOT NULL DEFAULT '-2',
  `addPoll` tinyint(1) NOT NULL DEFAULT '-2',
  `addRolls` tinyint(1) NOT NULL DEFAULT '-2',
  `addDraws` tinyint(1) NOT NULL DEFAULT '-2',
  `moderate` tinyint(1) NOT NULL DEFAULT '-2',
  PRIMARY KEY (`groupID`,`forumID`),
  KEY `forumID` (`forumID`)
);

CREATE TABLE `forums_permissions_users` (
  `userID` int NOT NULL,
  `forumID` int NOT NULL,
  `read` tinyint(1) NOT NULL DEFAULT '0',
  `write` tinyint(1) NOT NULL DEFAULT '0',
  `editPost` tinyint(1) NOT NULL DEFAULT '0',
  `deletePost` tinyint(1) NOT NULL DEFAULT '0',
  `createThread` tinyint(1) NOT NULL DEFAULT '0',
  `deleteThread` tinyint(1) NOT NULL DEFAULT '0',
  `addPoll` tinyint(1) NOT NULL DEFAULT '0',
  `addRolls` tinyint(1) NOT NULL DEFAULT '0',
  `addDraws` tinyint(1) NOT NULL DEFAULT '0',
  `moderate` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`userID`,`forumID`),
  KEY `forumID` (`forumID`)
);

CREATE TABLE `forums_pollOptions` (
  `pollOptionID` int NOT NULL AUTO_INCREMENT,
  `threadID` int NOT NULL,
  `option` varchar(200) NOT NULL,
  PRIMARY KEY (`pollOptionID`)
);

CREATE TABLE `forums_pollVotes` (
  `userID` int NOT NULL,
  `pollOptionID` int NOT NULL,
  `votedOn` datetime NOT NULL,
  PRIMARY KEY (`userID`,`pollOptionID`)
);

CREATE TABLE `forums_polls` (
  `threadID` int NOT NULL,
  `poll` varchar(200) NOT NULL,
  `optionsPerUser` tinyint NOT NULL DEFAULT '1',
  `pollLength` tinyint DEFAULT NULL,
  `allowRevoting` tinyint(1) NOT NULL,
  PRIMARY KEY (`threadID`)
);

CREATE TABLE `forums_postFFGFlips` (
  `flipID` int NOT NULL AUTO_INCREMENT,
  `postID` int NOT NULL,
  `userID` int NOT NULL,
  `toDark` int NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`flipID`)
);

CREATE TABLE `forums_postPollVotes` (
  `postID` int NOT NULL,
  `userID` int NOT NULL,
  `vote` int NOT NULL,
  PRIMARY KEY (`postID`,`userID`,`vote`)
);

CREATE TABLE `forums_readData` (
  `userID` int NOT NULL,
  `forumData` longtext NOT NULL,
  `threadData` longtext NOT NULL,
  PRIMARY KEY (`userID`)
);

CREATE TABLE `forums_readData_forums` (
  `userID` int NOT NULL,
  `forumID` int NOT NULL,
  `markedRead` int NOT NULL,
  PRIMARY KEY (`userID`,`forumID`)
);

CREATE TABLE `forums_readData_threads` (
  `userID` int NOT NULL,
  `threadID` int NOT NULL,
  `lastRead` int NOT NULL,
  PRIMARY KEY (`userID`,`threadID`)
);

CREATE TABLE `gameHistory` (
  `actionID` int NOT NULL AUTO_INCREMENT,
  `gameID` int NOT NULL,
  `enactedBy` int NOT NULL,
  `enactedOn` datetime NOT NULL,
  `action` varchar(20) NOT NULL,
  `affectedType` varchar(20) DEFAULT NULL,
  `affectedID` int DEFAULT NULL,
  PRIMARY KEY (`actionID`)
);

CREATE TABLE `gameInvites` (
  `gameID` int NOT NULL,
  `userID` int NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`gameID`,`userID`)
);

CREATE TABLE `games` (
  `gameID` int NOT NULL AUTO_INCREMENT,
  `title` varchar(100) NOT NULL,
  `system` varchar(30) NOT NULL,
  `customSystem` varchar(100) DEFAULT NULL,
  `gmID` int NOT NULL,
  `created` datetime NOT NULL,
  `start` datetime NOT NULL,
  `end` datetime DEFAULT NULL,
  `postFrequency` json NOT NULL,
  `numPlayers` tinyint NOT NULL,
  `charsPerPlayer` tinyint NOT NULL DEFAULT '1',
  `description` longtext NOT NULL,
  `charGenInfo` longtext NOT NULL,
  `forumID` int DEFAULT NULL,
  `groupID` int NOT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `public` tinyint(1) NOT NULL,
  `retired` datetime DEFAULT NULL,
  `allowedCharSheets` json NOT NULL,
  `gameOptions` json DEFAULT NULL,
  `recruitmentThreadId` int DEFAULT NULL,
  PRIMARY KEY (`gameID`),
  KEY `gmID` (`gmID`),
  KEY `forumID` (`forumID`),
  KEY `groupID` (`groupID`)
);

CREATE TABLE `games_favorites` (
  `userID` int NOT NULL,
  `gameID` int NOT NULL,
  PRIMARY KEY (`userID`,`gameID`)
);

CREATE TABLE `lfg` (
  `userID` int NOT NULL,
  `system` varchar(30) NOT NULL,
  PRIMARY KEY (`userID`,`system`),
  UNIQUE KEY `userID` (`userID`,`system`) USING BTREE
);

CREATE TABLE `loginRecords` (
  `userID` int NOT NULL,
  `attemptStamp` datetime NOT NULL,
  `ipAddress` varchar(15) NOT NULL,
  `successful` tinyint(1) NOT NULL,
  PRIMARY KEY (`userID`,`attemptStamp`)
);

CREATE TABLE `mapData` (
  `mapID` int NOT NULL,
  `col` tinyint NOT NULL,
  `row` tinyint NOT NULL,
  `data` longtext,
  PRIMARY KEY (`mapID`,`col`,`row`)
);

CREATE TABLE `maps` (
  `mapID` int NOT NULL AUTO_INCREMENT,
  `gameID` int NOT NULL,
  `name` varchar(50) NOT NULL,
  `rows` tinyint NOT NULL,
  `cols` tinyint NOT NULL,
  `info` varchar(300) NOT NULL,
  `visible` tinyint(1) NOT NULL,
  `deleted` tinyint(1) NOT NULL,
  PRIMARY KEY (`mapID`)
);

CREATE TABLE `maps_iconHistory` (
  `actionID` int NOT NULL AUTO_INCREMENT,
  `iconID` int NOT NULL,
  `mapID` int NOT NULL,
  `enactedBy` int NOT NULL,
  `enactedOn` datetime NOT NULL,
  `action` varchar(20) NOT NULL,
  `origin` varchar(10) DEFAULT NULL,
  `destination` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`actionID`)
);

CREATE TABLE `maps_icons` (
  `iconID` int NOT NULL AUTO_INCREMENT,
  `mapID` int NOT NULL,
  `label` varchar(2) NOT NULL,
  `name` varchar(50) NOT NULL,
  `description` varchar(200) NOT NULL,
  `color` varchar(6) NOT NULL,
  `location` varchar(7) NOT NULL,
  `deleted` tinyint(1) NOT NULL,
  PRIMARY KEY (`iconID`)
);

CREATE TABLE `marvel_actionsList` (
  `actionID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `searchName` varchar(50) DEFAULT NULL,
  `cost` tinyint NOT NULL,
  `magic` tinyint(1) NOT NULL,
  `source` varchar(50) NOT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`actionID`)
);

CREATE TABLE `marvel_modifiersList` (
  `modifierID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `searchName` varchar(50) DEFAULT NULL,
  `cost` float NOT NULL,
  `costTo` varchar(5) NOT NULL,
  `multipleAllowed` varchar(40) NOT NULL,
  `source` varchar(50) NOT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`modifierID`)
);

CREATE TABLE `music` (
  `id` int NOT NULL AUTO_INCREMENT,
  `url` text NOT NULL,
  `title` varchar(200) NOT NULL,
  `lyrics` tinyint(1) NOT NULL DEFAULT '0',
  `genres` json DEFAULT NULL,
  `notes` text,
  `approved` tinyint(1) NOT NULL DEFAULT '0',
  `user` int NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `notifications` (
  `notificationID` int NOT NULL AUTO_INCREMENT,
  `category` varchar(20) NOT NULL,
  `enactedBy` int NOT NULL,
  `enactedOn` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actedUpon` int NOT NULL,
  PRIMARY KEY (`notificationID`)
);

CREATE TABLE `players` (
  `gameID` int NOT NULL,
  `userID` int NOT NULL,
  `approved` tinyint(1) NOT NULL DEFAULT '0',
  `isGM` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`gameID`,`userID`)
);

CREATE TABLE `pms` (
  `pmID` int NOT NULL AUTO_INCREMENT,
  `recipientID` int NOT NULL,
  `senderID` int NOT NULL,
  `title` varchar(200) NOT NULL,
  `message` mediumtext NOT NULL,
  `datestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `recipientRead` tinyint(1) NOT NULL DEFAULT '0',
  `senderRead` tinyint(1) NOT NULL DEFAULT '0',
  `replyTo` int DEFAULT NULL,
  `recipientDeleted` tinyint(1) NOT NULL DEFAULT '0',
  `senderDeleted` tinyint(1) NOT NULL DEFAULT '0',
  `history` json DEFAULT NULL,
  PRIMARY KEY (`pmID`),
  KEY `recipientID` (`recipientID`),
  KEY `senderID` (`senderID`)
);

CREATE TABLE `posts` (
  `postID` int NOT NULL AUTO_INCREMENT,
  `threadID` int NOT NULL,
  `title` varchar(100) NOT NULL,
  `authorID` int NOT NULL,
  `message` longtext NOT NULL,
  `datePosted` datetime NOT NULL,
  `lastEdit` datetime DEFAULT NULL,
  `timesEdited` tinyint NOT NULL DEFAULT '0',
  `postAs` int DEFAULT NULL,
  `messageFullText` longtext,
  PRIMARY KEY (`postID`),
  KEY `threadID` (`threadID`),
  KEY `authorID` (`authorID`),
  KEY `datePosted` (`datePosted`),
  FULLTEXT KEY `messageFullText` (`messageFullText`)
);

CREATE TABLE `privilages` (
  `userID` int NOT NULL,
  `privilage` varchar(20) NOT NULL,
  PRIMARY KEY (`userID`,`privilage`)
);

CREATE TABLE `referralLinks` (
  `key` varchar(255) NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `link` varchar(255) DEFAULT NULL,
  `order` int DEFAULT NULL,
  PRIMARY KEY (`key`)
);

CREATE TABLE `rolls` (
  `rollID` int NOT NULL AUTO_INCREMENT,
  `postID` int NOT NULL,
  `type` varchar(12) NOT NULL,
  `reason` varchar(100) NOT NULL,
  `roll` varchar(50) NOT NULL,
  `indivRolls` varchar(500) NOT NULL,
  `results` varchar(250) DEFAULT NULL,
  `visibility` tinyint(1) NOT NULL,
  `extras` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`rollID`),
  KEY `postID` (`postID`)
);

CREATE TABLE `skillsList` (
  `skillID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `searchName` varchar(50) DEFAULT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`skillID`),
  UNIQUE KEY `name` (`name`)
);

CREATE TABLE `spycraft2_focusesList` (
  `focusID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `searchName` varchar(50) DEFAULT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`focusID`)
);

CREATE TABLE `starwarsffg_talentsList` (
  `talentID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `searchName` varchar(50) NOT NULL,
  `userDefined` int DEFAULT NULL,
  PRIMARY KEY (`talentID`),
  UNIQUE KEY `name` (`name`)
);

CREATE TABLE `system_charAutocomplete_map` (
  `systemID` int NOT NULL,
  `system` varchar(30) NOT NULL,
  `itemID` int NOT NULL,
  PRIMARY KEY (`systemID`,`itemID`)
);

CREATE TABLE `systems` (
  `id` varchar(20) NOT NULL,
  `name` varchar(40) NOT NULL,
  `sortName` varchar(40) NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `angular` tinyint(1) NOT NULL DEFAULT '1',
  `genres` json DEFAULT NULL,
  `publisher` json DEFAULT NULL,
  `basics` json DEFAULT NULL,
  `hasCharSheet` tinyint(1) NOT NULL DEFAULT '1',
  `lfg` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
);

CREATE TABLE `threads` (
  `threadID` int NOT NULL AUTO_INCREMENT,
  `forumID` int NOT NULL,
  `sticky` tinyint(1) NOT NULL,
  `locked` tinyint(1) NOT NULL,
  `allowRolls` tinyint(1) NOT NULL,
  `allowDraws` tinyint(1) NOT NULL,
  `firstPostID` int NOT NULL,
  `lastPostID` int NOT NULL,
  `postCount` int NOT NULL,
  `publicPosting` tinyint(1) NOT NULL,
  `discordWebhook` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`threadID`),
  KEY `forumID` (`forumID`),
  KEY `lastPostID` (`lastPostID`)
);

CREATE TABLE `userAddedItems` (
  `uItemID` int NOT NULL AUTO_INCREMENT,
  `itemType` varchar(10) NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  `itemID` int DEFAULT NULL,
  `addedBy` int NOT NULL,
  `addedOn` datetime NOT NULL,
  `systemID` int DEFAULT NULL,
  `system` varchar(30) DEFAULT NULL,
  `action` varchar(10) DEFAULT NULL,
  `actedBy` int DEFAULT NULL,
  `actedOn` datetime DEFAULT NULL,
  PRIMARY KEY (`uItemID`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `itemID` (`itemID`,`systemID`),
  UNIQUE KEY `name_2` (`name`),
  UNIQUE KEY `itemID_2` (`itemID`,`systemID`)
);

CREATE TABLE `userHistory` (
  `actionID` int NOT NULL AUTO_INCREMENT,
  `userID` int NOT NULL,
  `enactedBy` int NOT NULL,
  `enactedOn` datetime NOT NULL,
  `action` varchar(30) NOT NULL,
  `additionalInfo` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`actionID`)
);

CREATE TABLE `usermeta` (
  `metaID` int NOT NULL AUTO_INCREMENT,
  `userID` int NOT NULL,
  `metaKey` varchar(50) NOT NULL,
  `metaValue` longtext NOT NULL,
  `autoload` tinyint(1) NOT NULL,
  PRIMARY KEY (`metaID`),
  UNIQUE KEY `userID` (`userID`,`metaKey`),
  KEY `autoload` (`autoload`)
);

CREATE TABLE `users` (
  `userID` int NOT NULL AUTO_INCREMENT,
  `username` varchar(24) NOT NULL,
  `password` varchar(64) NOT NULL,
  `salt` varchar(20) NOT NULL,
  `email` varchar(50) NOT NULL,
  `joinDate` datetime NOT NULL,
  `activatedOn` datetime DEFAULT NULL,
  `lastActivity` datetime DEFAULT NULL,
  `enableFilter` tinyint(1) NOT NULL DEFAULT '1',
  `timezone` varchar(20) NOT NULL DEFAULT 'Europe/London',
  `suspendedUntil` datetime DEFAULT NULL,
  `banned` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`userID`),
  UNIQUE KEY `username` (`username`)
);

CREATE TABLE `wordFilter` (
  `wordID` int NOT NULL AUTO_INCREMENT,
  `word` varchar(50) NOT NULL,
  `spam` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`wordID`)
);

CREATE VIEW `forums_permissions` AS select 'general' AS `type`,0 AS `typeID`,`forums_permissions_general`.`forumID` AS `forumID`,`forums_permissions_general`.`read` AS `read`,`forums_permissions_general`.`write` AS `write`,`forums_permissions_general`.`editPost` AS `editPost`,`forums_permissions_general`.`deletePost` AS `deletePost`,`forums_permissions_general`.`createThread` AS `createThread`,`forums_permissions_general`.`deleteThread` AS `deleteThread`,`forums_permissions_general`.`addPoll` AS `addPoll`,`forums_permissions_general`.`addRolls` AS `addRolls`,`forums_permissions_general`.`addDraws` AS `addDraws`,`forums_permissions_general`.`moderate` AS `moderate` from `forums_permissions_general` union select 'group' AS `type`,`forums_permissions_groups`.`groupID` AS `typeID`,`forums_permissions_groups`.`forumID` AS `forumID`,`forums_permissions_groups`.`read` AS `read`,`forums_permissions_groups`.`write` AS `write`,`forums_permissions_groups`.`editPost` AS `editPost`,`forums_permissions_groups`.`deletePost` AS `deletePost`,`forums_permissions_groups`.`createThread` AS `createThread`,`forums_permissions_groups`.`deleteThread` AS `deleteThread`,`forums_permissions_groups`.`addPoll` AS `addPoll`,`forums_permissions_groups`.`addRolls` AS `addRolls`,`forums_permissions_groups`.`addDraws` AS `addDraws`,`forums_permissions_groups`.`moderate` AS `moderate` from `forums_permissions_groups` union select 'user' AS `type`,`forums_permissions_users`.`userID` AS `typeID`,`forums_permissions_users`.`forumID` AS `forumID`,`forums_permissions_users`.`read` AS `read`,`forums_permissions_users`.`write` AS `write`,`forums_permissions_users`.`editPost` AS `editPost`,`forums_permissions_users`.`deletePost` AS `deletePost`,`forums_permissions_users`.`createThread` AS `createThread`,`forums_permissions_users`.`deleteThread` AS `deleteThread`,`forums_permissions_users`.`addPoll` AS `addPoll`,`forums_permissions_users`.`addRolls` AS `addRolls`,`forums_permissions_users`.`addDraws` AS `addDraws`,`forums_permissions_users`.`moderate` AS `moderate` from `forums_permissions_users`;

CREATE VIEW `forums_permissions_groups_c` AS select `gm`.`userID` AS `userID`,`gp`.`forumID` AS `forumID`,if((max(`gp`.`read`) = 2),2,min(`gp`.`read`)) AS `read`,if((max(`gp`.`write`) = 2),2,min(`gp`.`write`)) AS `write`,if((max(`gp`.`editPost`) = 2),2,min(`gp`.`editPost`)) AS `editPost`,if((max(`gp`.`deletePost`) = 2),2,min(`gp`.`deletePost`)) AS `deletePost`,if((max(`gp`.`createThread`) = 2),2,min(`gp`.`createThread`)) AS `createThread`,if((max(`gp`.`deleteThread`) = 2),2,min(`gp`.`deleteThread`)) AS `deleteThread`,if((max(`gp`.`addPoll`) = 2),2,min(`gp`.`addPoll`)) AS `addPoll`,if((max(`gp`.`addRolls`) = 2),2,min(`gp`.`addRolls`)) AS `addRolls`,if((max(`gp`.`addDraws`) = 2),2,min(`gp`.`addDraws`)) AS `addDraws`,if((max(`gp`.`moderate`) = 2),2,min(`gp`.`moderate`)) AS `moderate` from (`forums_groupMemberships` `gm` join `forums_permissions_groups` `gp` on((`gm`.`groupID` = `gp`.`groupID`))) group by `gp`.`forumID`,`gm`.`userID`;

CREATE VIEW `threads_relPosts` AS select `posts`.`threadID` AS `threadID`,min(`posts`.`postID`) AS `firstPostID`,max(`posts`.`postID`) AS `lastPostID` from `posts` group by `posts`.`threadID`;

CREATE VIEW `userPosts` AS select `posts`.`authorID` AS `userID`,count(0) AS `numPosts` from `posts` group by `posts`.`authorID`;
