# %%
#!python3

import os
import re
from typing import Union
from pathlib import Path
import logging

# Configuration
# 
rpyxPathToProcessList = [ "../../Systems/CVI3/CVI3.rpyx" ]



class RhpRpyx:
    """represents a Rhp project files"""

    def __init__( self, path : str ):

        self.absPath : str = os.path.abspath( path )
        self.exists : bool = os.path.exists( self.absPath )
        self.linksDico : dict[ str, RhpRpyx ] = dict()
        self.replacementsDico : dict[ str, str ] = dict()


    def trace(self):

        # recherche des réf de rpyx au dico
        logging.info( "Links of " + self.absPath)

        for link, rpyx in self.linksDico.items():
            
            # is there a replacement for this link
            replacedStr = self.rpyxToMatch( link )
            newStr = self.replacementsDico.get( replacedStr )

            logging.log( 
                ( logging.WARNING if not rpyx.exists else logging.INFO if newStr is not None else logging.DEBUG ),
                "    " + replacedStr + 
                ( " folder exists" if rpyx.exists else " does not exists" ) +
                ( " => " + newStr if newStr != None else "" ) )


    def getLinkedRpyx( self ) -> 'dict[str, RhpRpyx]':
        """   read the file to get all links toward other rhpRpyx
        """

        try:
            with open( self.absPath, 'r' ) as openRpyx:
                self.fileContent = openRpyx.read()

        except IOError as ioex:
            logging.error("Error reading file %s : %s", self.absPath, ioex)
            raise ioex

        # recherche des réf de rpyx
        matchs = re.findall( ">.*_rpy<", self.fileContent ) 

        # transform links to point to the rpyx file
        rhpLinksStr = ( self.matchToRpyx( match ) for match in matchs )
        
        # build the dictionary of the linked Rpyx
        # absolute path of the parent Rpyx is used in case a relative path is used for the linked Rpyx
        rhpRpyxFiles =  { rhpLink :  RhpRpyx( rhpLink ) if os.path.isabs( rhpLink ) 
                else RhpRpyx( self.joinRelativePath( rhpLink ) )
            for rhpLink 
            in rhpLinksStr }

        return rhpRpyxFiles
        
        
    def joinRelativePath( self, relativePath : str) -> str:
        """retourne le chemin absolu d'un lien sur un Rpyx à partir du chemin absolu de ce rpyx"""
        return os.path.normpath( os.path.join( Path( self.absPath ).absolute(), relativePath ) )

    def matchToRpyx( self, match : str ) -> str:
        return ( match.lstrip('>').rstrip('<').replace("_rpy", "", 1) + ".rpyx" )

    def rpyxToMatch( self, rpyx : str ) -> str:
        return ( '>' + rpyx.replace(".rpyx", "", 1) + "_rpy<" )

    def linkRpyx( self, inFilePath : str, newRpyx : 'RhpRpyx' ):
        self.linksDico[ inFilePath ] = newRpyx     

    def prepareReplacements( self ):
        self.replacementsDico = {
            self.rpyxToMatch( rhpLink ) : self.rpyxToMatch( os.path.relpath( rhpLink, Path( self.absPath ).absolute() ) )
            for rhpLink in self.linksDico.keys() if os.path.isabs( rhpLink )
        }

    def doReplacements( self ):
        """writes replacements from self.replacementsDico into the rpyx file"""

        newContent : str = self.fileContent

        for oldStr, newStr in self.replacementsDico.items():
            newContent = newContent.replace( oldStr, newStr )

        try:
            with open( self.absPath, 'w' ) as openRpyx:
                openRpyx.write( newContent )

        except IOError as ioex:
            logging.error("Error writing file %s : %s", self.absPath, ioex)
            raise ioex


class ReplacementStrategy:
    """Stratégie abstraite de remplacement des liens"""
    def prepareAndCountReplacements( self, rhpRpyx : RhpRpyx ):
        pass

    def doReplacements( self, rhpRpyx : RhpRpyx ):
        pass


class RelativePathReplacementStrategy( ReplacementStrategy ):
    """Stratégie de remplacement des liens, passage en chemin relatif"""

    def __init__(self, maxFileToUpdate : int) -> None:
        super().__init__()
        self.linkCount : int = 0
        self.replacementCount : int = 0
        self.fileUpdatedCount : int = 0
        self.updatedFileCount : int = 0
        self.maxFileToUpdate : int = maxFileToUpdate

    def prepareAndCountReplacements( self, rhpRpyx : RhpRpyx ):
        """Ne remplace que les chemins absolus"""
        rhpRpyx.prepareReplacements()

        nbReplacement = len( rhpRpyx.replacementsDico )
        self.replacementCount += nbReplacement
        self.linkCount += len( rhpRpyx.linksDico )
        if nbReplacement >= 1:
            self.fileUpdatedCount += 1


    def doReplacements( self, rhpRpyx : RhpRpyx ):
        """Effectue les remplacements dans le rpyx physique"""

        if not rhpRpyx.exists:
            logging.debug( f"Ignoring file {rhpRpyx.absPath}, as it does not exist" )
            return

        replacementCount = len( rhpRpyx.replacementsDico )
        if replacementCount == 0:
            logging.debug( f"Skipping file {rhpRpyx.absPath}, as there is no replacement to do" )
            return

        if ( self.updatedFileCount < self.maxFileToUpdate ):
            rhpRpyx.doReplacements()

        logging.debug( f"{replacementCount} replacements written in file {rhpRpyx.absPath}" )

        self.updatedFileCount += 1




# represents a rpyx index, files are indexed with their absolute file path
#
class RhpIndex:

    def __init__( self ):
        self.indexByAbsPath : dict[ str, RhpRpyx ] = dict()

    # get an indexed RhpRpyx
    def getIndexedRhpyx( self, absolutePath : str ) -> Union[RhpRpyx, None]:
        lowerAbsPath = absolutePath.lower()
        return self.indexByAbsPath.get( lowerAbsPath )


    # add an indexed RhpRpyx, and get it
    def addIndexedRhpyx( self, rpyx : RhpRpyx ):

        lowerAbsPath = rpyx.absPath.lower()

        indexedRpyx = self.indexByAbsPath.get( lowerAbsPath )

        if None == indexedRpyx:
            logging.debug( "Adding " + lowerAbsPath + " to index" )
            self.indexByAbsPath[ lowerAbsPath ] = rpyx
            

class RhpLinksUpdater():

    """
    Update Rhp links from absolute file path to relative file path
    """
    def __init__(self, replacementStrategy : ReplacementStrategy ) -> None:
        self.replacementStrategy : ReplacementStrategy = replacementStrategy
        self.rhpIndex : RhpIndex = RhpIndex()

    def update( self ):

        # do work from the list in rpyxPathToProcessList
        for rpyxPathToProcess in rpyxPathToProcessList:
            
            logging.info( "Apply '%s' to file %s", type(replaceStrategy).__name__, rpyxPathToProcess )
            rhpRpyx = RhpRpyx( rpyxPathToProcess )
            self.rhpIndex.getIndexedRhpyx( rhpRpyx.absPath )

            if not rhpRpyx.exists:
                #  logging.warning("\033[33m"+ rhpRpyx.absPath+ " does not exist\033[39m")
                logging.warning( rhpRpyx.absPath+ " does not exist")
            else:
                self.searchLinks( rhpRpyx )

        # on effectue les remplacements:
        for indexedRpyx in self.rhpIndex.indexByAbsPath.values():
            self.replacementStrategy.doReplacements( indexedRpyx )


    def searchLinks( self, existingRhpRpyx : RhpRpyx, maxDepth : int = -1  ):
        """
        Recherche des liens d'un RhpRpyx vers d'autres RhpRpyx 
        """

        # get RhpxLinks as they are written in the file rhpRpyx
        linkedRpyxDico = existingRhpRpyx.getLinkedRpyx()

        alreadyIndexedRpyx : Union[RhpRpyx, None] = None

        listNewRpyxToSearchLinks : list[RhpRpyx] = list()

        # index all rhpRpyx links if they are note already indexed
        for inFileRhpxLink, linkedRpyx in linkedRpyxDico.items():
            
            # build absolute path from
            alreadyIndexedRpyx = self.rhpIndex.getIndexedRhpyx( linkedRpyx.absPath )

            # add the Rpyx
            existingRhpRpyx.linkRpyx( inFileRhpxLink, alreadyIndexedRpyx or linkedRpyx )

            # add to index 
            if None == alreadyIndexedRpyx:

                self.rhpIndex.addIndexedRhpyx( linkedRpyx ) 

                # add this rpyx to the list to search link
                if linkedRpyx.exists:
                    listNewRpyxToSearchLinks.append( linkedRpyx )

        # prepare les remplacements 
        self.replacementStrategy.prepareAndCountReplacements( existingRhpRpyx )
                    
        # for rhpLink in existingRhpRpyx.linksDico.values():
        existingRhpRpyx.trace()

        # read recursively linked rpyxfiles
        if maxDepth != 0:
            for notSearchedRpyx in listNewRpyxToSearchLinks:
                self.searchLinks( notSearchedRpyx, maxDepth -1 )
        




if (__name__ == '__main__'):
    """
    main function
    """
    logging.basicConfig( filename='update_rpyx_link.log', filemode='w', level=logging.DEBUG, format='%(levelname)s:%(message)s' )

    replaceStrategy = RelativePathReplacementStrategy( maxFileToUpdate = 0 )
    rhpLinksUpdater = RhpLinksUpdater( replaceStrategy )
    rhpLinksUpdater.update()

    logging.info( "Number of updated files: %s", replaceStrategy.fileUpdatedCount )
    logging.info( "Number of links between files: %s", replaceStrategy.linkCount )
    logging.info( "Number of replacements among all these links: %s", replaceStrategy.replacementCount )




# %%
